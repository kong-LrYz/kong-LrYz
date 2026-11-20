"""Refresh the README's latest pushes from GitHub's public repository list."""

import json
from datetime import datetime, timezone
from pathlib import Path
import re
import sys


def refresh(readme, pages, owner):
    start = "<!-- activity:start -->\n"
    end = "<!-- activity:end -->"
    before, start_marker, rest = readme.partition(start)
    _, end_marker, after = rest.partition(end)
    if readme.count(start) != 1 or readme.count(end) != 1 or not end_marker:
        raise ValueError("Expected one pair of ordered activity markers in README.md")

    rows = []
    for page in pages:
        for repo in page:
            name = repo["name"]
            if (
                repo["private"]
                or repo["fork"]
                or repo["archived"]
                or not repo["pushed_at"]
                or name.casefold() == owner.casefold()
            ):
                continue
            if not re.fullmatch(r"[A-Za-z0-9_.-]+", name):
                raise ValueError(f"Unexpected GitHub repository name: {name!r}")
            pushed_at = datetime.fromisoformat(repo["pushed_at"]).astimezone(timezone.utc)
            rows.append((pushed_at, name))

    entries = [
        f"- [`{name}`](https://github.com/{owner}/{name}) · {pushed_at:%Y-%m-%d}"
        for pushed_at, name in sorted(rows, reverse=True)[:3]
    ]
    activity = "\n".join(entries) or "_No public repository pushes to display yet._"
    return f"{before}{start_marker}\n{activity}\n\n{end_marker}{after}"


if __name__ == "__main__":
    owner = sys.argv[1]
    if not re.fullmatch(r"[A-Za-z0-9-]+", owner):
        raise SystemExit("Expected a GitHub account login")

    readme_path = Path("README.md")
    original = readme_path.read_text(encoding="utf-8")
    updated = refresh(original, json.load(sys.stdin), owner)
    if updated != original:
        readme_path.write_text(updated, encoding="utf-8")
