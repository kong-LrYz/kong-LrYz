"""Render the profile's contribution animation and its reduced-motion image."""

import argparse
from datetime import date, timedelta
from html.parser import HTMLParser
from math import cos, hypot, pi, sin
from pathlib import Path
from random import Random
import re
from urllib.request import Request, urlopen

from PIL import Image, ImageDraw, ImageFont

WIDTH, HEIGHT = 1040, 392
WEEKS = 26
FPS = 30
SECONDS = 10
COLORS = ("#15243a", "#194352", "#1c6f72", "#32a89b", "#85efd0")
INK = "#e7f8f7"
MUTED = "#9caec6"
TEAL = "#80f8dd"
PEACH = "#ffd9a5"


class ContributionCalendar(HTMLParser):
    def __init__(self):
        super().__init__()
        self.levels = {}

    def handle_starttag(self, tag, attributes):
        attrs = dict(attributes)
        if tag != "td" or "ContributionCalendar-day" not in attrs.get("class", "").split():
            return
        level = int(attrs["data-level"])
        if level not in range(len(COLORS)):
            raise ValueError(f"Unexpected contribution level: {level}")
        self.levels[date.fromisoformat(attrs["data-date"])] = level


def read_calendar(owner):
    # Use the same calendar that GitHub serves to signed-out profile visitors.
    request = Request(
        f"https://github.com/users/{owner}/contributions",
        headers={"User-Agent": "Profile-Reactor/1.0"},
    )
    with urlopen(request, timeout=25) as response:
        parser = ContributionCalendar()
        parser.feed(response.read().decode("utf-8"))
    if not parser.levels:
        raise ValueError("GitHub returned no contribution calendar cells")

    last = max(parser.levels)
    first = last - timedelta(days=(last.weekday() + 1) % 7 + (WEEKS - 1) * 7)
    days = [first + timedelta(days=index) for index in range((last - first).days + 1)]
    if any(day not in parser.levels for day in days):
        raise ValueError("GitHub returned an incomplete contribution calendar")
    return first, last, {day: parser.levels[day] for day in days}


def font(size):
    return ImageFont.load_default(size=size)


def blend(a, b, amount):
    return a + (b - a) * amount


def smooth(value):
    return value * value * (3 - 2 * value)


def circle(draw, x, y, radius, color, width=0):
    bounds = (x - radius, y - radius, x + radius, y + radius)
    if width:
        draw.ellipse(bounds, outline=color, width=width)
    else:
        draw.ellipse(bounds, fill=color)


def tint(color, alpha):
    return (*color, max(0, min(255, round(alpha))))


CYAN_RGB = (104, 249, 215)
AMBER_RGB = (255, 192, 130)


def tile_position(week, weekday):
    return 85 + 35 * week, 164 + 24 * weekday


def render_board(first, last, levels, owner):
    base = Image.new("RGB", (WIDTH, HEIGHT))
    draw = ImageDraw.Draw(base)
    for y in range(HEIGHT):
        gradient = y / HEIGHT
        draw.line((0, y, WIDTH, y), fill=(round(12 - 4 * gradient), round(22 - 8 * gradient), round(38 - 13 * gradient)))

    draw.rounded_rectangle((1, 1, WIDTH - 2, HEIGHT - 2), 22, outline="#2d4057", width=2)
    draw.line((45, 119, 995, 119), fill="#28394f")
    draw.line((45, 339, 995, 339), fill="#28394f")

    circle(draw, 51, 37, 4, TEAL)
    draw.text((64, 36), "GITHUB CONTRIBUTIONS", font=font(15), fill=TEAL, anchor="lm")
    draw.text((45, 77), "Commit Reactor", font=font(54), fill=INK, anchor="lm", stroke_width=1)
    draw.text((991, 48), f"@{owner}", font=font(24), fill=INK, anchor="rm")
    draw.text((991, 82), f"{WEEKS} weeks", font=font(19), fill=MUTED, anchor="rm")

    for weekday, label in ((1, "MON"), (3, "WED"), (5, "FRI")):
        _, y = tile_position(0, weekday)
        draw.text((43, y), label, font=font(11), fill=MUTED, anchor="lm")

    points = []
    for week in range(WEEKS):
        week_start = first + timedelta(weeks=week)
        x, _ = tile_position(week, 0)
        if week == 0 or week_start.month != (week_start - timedelta(weeks=1)).month:
            draw.text((x, 137), week_start.strftime("%b").upper(), font=font(14), fill=MUTED, anchor="lm")

        for weekday in range(7):
            day = week_start + timedelta(days=weekday)
            if day not in levels:
                continue
            level = levels[day]
            x, y = tile_position(week, weekday)
            draw.rounded_rectangle((x - 12, y - 8, x + 12, y + 8), 4, fill=COLORS[level])
            if level > 2:
                draw.line((x - 6, y - 5, x + 6, y - 5), fill="#9cf6d7")
            if level:
                points.append((x, y, level))

    draw.text((45, 365), f"{first:%d %b %Y}  to  {last:%d %b %Y}", font=font(18), fill=MUTED, anchor="lm")
    draw.text((789, 365), "Less", font=font(17), fill=MUTED, anchor="rm")
    for index, color in enumerate(COLORS):
        x = 799 + 27 * index
        draw.rounded_rectangle((x, 356, x + 20, 374), 4, fill=color)
    draw.text((995, 365), "More", font=font(17), fill=MUTED, anchor="rm")
    return base, points


def flight_path(points):
    # Pick active cells near three evenly spaced points so the camera never moves.
    if not points:
        points = [(*tile_position(week, day), 0) for week, day in ((4, 2), (12, 5), (22, 1))]
    hotspots = []
    for target_x, target_y in ((225, 193), (515, 278), (837, 208)):
        remaining = [point for point in points if point not in hotspots]
        if not remaining:
            break
        hotspots.append(min(remaining, key=lambda p: abs(p[0] - target_x) + 0.6 * abs(p[1] - target_y) - 5 * p[2]))
    return [point[:2] for point in hotspots]


def robot_position(t, route):
    for (start, x0, y0), (end, x1, y1) in zip(route, route[1:]):
        if t <= end:
            progress = (t - start) / (end - start)
            eased = smooth(progress)
            return blend(x0, x1, eased), blend(y0, y1, eased) - 16 * sin(pi * progress)
    return route[-1][1:]


def draw_robot(frame, t, route):
    draw = ImageDraw.Draw(frame, "RGBA")
    for index in range(14, 0, -1):
        x, y = robot_position((t - 0.033 * index) % SECONDS, route)
        circle(draw, x, y, max(1, 4 - index * 0.19), tint(CYAN_RGB, 135 - index * 8))

    x, y = robot_position(t, route)
    for radius, alpha in ((24, 12), (19, 21), (15, 38)):
        circle(draw, x, y, radius, tint(CYAN_RGB, alpha))
    circle(draw, x, y, 12, "#111c31")
    circle(draw, x, y, 12, TEAL, width=2)
    draw.line((x - 17, y, x - 11, y), fill=TEAL, width=2)
    draw.line((x + 11, y, x + 17, y), fill=TEAL, width=2)
    draw.rounded_rectangle((x - 6, y - 3, x + 6, y + 3), 3, fill=INK)


def draw_charge(frame, t, start, center, particles, nearby_tiles):
    elapsed = t - start
    if not 0 <= elapsed < 1.5:
        return
    draw = ImageDraw.Draw(frame, "RGBA")
    x, y = center
    if elapsed < 0.48:
        progress = elapsed / 0.48
        circle(draw, x, y, blend(20, 8, progress), tint(AMBER_RGB, 190), width=2)
        circle(draw, x, y, blend(3, 7, progress), PEACH)
        return

    progress = (elapsed - 0.48) / 1.02
    radius = 12 + 75 * (1 - (1 - progress) ** 2)
    fade = (1 - progress) ** 1.6
    for tile_x, tile_y, distance in nearby_tiles:
        strength = max(0, 1 - abs(distance - radius) / 23) * fade
        if strength > 0:
            tile = (tile_x - 12, tile_y - 8, tile_x + 12, tile_y + 8)
            draw.rounded_rectangle(tile, 4, fill=tint(CYAN_RGB, strength * 180))
    circle(draw, x, y, radius + 8, tint(AMBER_RGB, 35 * fade), width=7)
    circle(draw, x, y, radius, tint(AMBER_RGB, 237 * fade), width=3)
    circle(draw, x, y, max(4, radius * 0.68), tint(CYAN_RGB, 180 * fade), width=2)
    circle(draw, x, y, 11 * (1 - progress) + 4, tint(AMBER_RGB, 228 * fade))

    for angle, distance, size in particles:
        travel = radius * distance
        px, py = x + cos(angle) * travel, y + sin(angle) * travel
        circle(draw, px, py, size * (1 - 0.7 * progress), tint(AMBER_RGB, 242 * fade))


def render_frames(base, points):
    centers = flight_path(points)
    launch_times = (2.0, 4.25, 6.55)
    route = [(0, 75, 252)]
    charges = []
    for index, ((x, y), start) in enumerate(zip(centers, launch_times)):
        route.append((start, x, y))
        random = Random(index)
        particles = [(random.uniform(0, 2 * pi), random.uniform(0.55, 1.25), random.uniform(1.5, 4)) for _ in range(24)]
        nearby_tiles = []
        for tile_x, tile_y, _ in points:
            distance = hypot(tile_x - x, tile_y - y)
            if distance <= 100:
                nearby_tiles.append((tile_x, tile_y, distance))
        charges.append((start, (x, y), particles, nearby_tiles))
    route.extend(((7.85, 961, 286), (8.15, 938, 316), (9.5, 100, 316), (SECONDS, 75, 252)))

    field_top, field_bottom = 151, 338
    header = base.crop((0, 0, WIDTH, field_top))
    footer = base.crop((0, field_bottom, WIDTH, HEIGHT))

    for index in range(FPS * SECONDS):
        time = index / FPS
        frame = base.copy()
        for start, center, particles, nearby_tiles in charges:
            draw_charge(frame, time, start, center, particles, nearby_tiles)
        draw_robot(frame, time, route)
        frame.paste(header, (0, 0))
        frame.paste(footer, (0, field_bottom))
        yield frame


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("owner")
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9-]+", args.owner):
        parser.error("Expected a GitHub account login")

    first, last, levels = read_calendar(args.owner)
    base, points = render_board(first, last, levels, args.owner)
    frames = render_frames(base, points)
    initial = next(frames)
    frame_duration = [round((index + 1) * 1000 / FPS) - round(index * 1000 / FPS) for index in range(FPS * SECONDS)]
    args.output.mkdir(parents=True, exist_ok=True)
    initial.save(args.output / "reactor-motion.webp", save_all=True, append_images=frames,
                 duration=frame_duration, loop=0, quality=86, method=4, minimize_size=True)
    initial.save(args.output / "reactor.webp", quality=90, method=6)
    print(f"Rendered {len(levels)} contribution days from {first} through {last}.")


if __name__ == "__main__":
    main()
