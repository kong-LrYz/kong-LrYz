"""Publish changed cards under content-based paths to avoid stale image caches."""

import hashlib
from pathlib import Path
import re
import sys


def publish(source: Path, root: Path) -> None:
    assets = root / "assets/visuals"
    readme_path = root / "README.md"
    readme = readme_path.read_text(encoding="utf-8")
    updates = {}
    obsolete = set()

    for mode in ("light", "dark"):
        snake = f"snake-{mode}.svg"
        updates[assets / snake] = (source / snake).read_bytes()

        for card in ("contribution-streak", "github-stats"):
            stem = f"{card}-{mode}"
            svg = (source / f"{stem}.svg").read_bytes()
            digest = hashlib.sha256(svg).hexdigest()[:16]
            name = f"{stem}-{digest}.svg"
            pattern = rf"(assets/visuals/)({re.escape(stem)}(?:-[0-9a-f]{{16}})?\.svg)(?=\")"
            match = re.search(pattern, readme)
            if match is None or len(re.findall(pattern, readme)) != 1:
                raise ValueError(f"Expected one README reference for {stem}")
            old = match.group(2)
            readme = readme[:match.start(2)] + name + readme[match.end(2):]
            updates[assets / name] = svg
            if old != name:
                obsolete.add(assets / old)

    updates[root / ".github/profile-fingerprint.txt"] = (source / "profile-fingerprint.txt").read_bytes()
    for path, contents in updates.items():
        path.write_bytes(contents)
    readme_path.write_text(readme, encoding="utf-8")
    for path in obsolete:
        path.unlink(missing_ok=True)


if __name__ == "__main__":
    publish(Path(sys.argv[1]), Path.cwd())
