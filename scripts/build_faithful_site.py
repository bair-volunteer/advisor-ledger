#!/usr/bin/env python3
"""Build the /faithful/ site: render a chosen list of snapshots with a shared
top-bar selector, and make the newest one the default landing page.

Add a new version by appending to SNAPSHOTS (oldest first) and re-running.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RENDERER = ROOT / "scripts" / "render_gdoc_faithful.py"
OUT_DIR = ROOT / "docs" / "faithful"

# Oldest first. The newest entry becomes index.html and is marked "最新".
SNAPSHOTS: list[dict] = [
    {
        "ts": "2026-04-20T20-55-10Z",
        "path": "snapshots/2026/04/20/source-1/2026-04-20T20-55-10Z.json",
    },
    {
        "ts": "2026-04-21T01-05-00Z",
        "path": "snapshots/2026/04/21/source-1/2026-04-21T01-05-00Z.json",
    },
]


def pretty(ts: str) -> str:
    """'2026-04-21T01-05-00Z' -> '2026-04-21 01:05:00 UTC'"""
    date, rest = ts.split("T", 1)
    return f"{date} {rest[:-1].replace('-', ':')} UTC"


def main() -> int:
    if not SNAPSHOTS:
        print("SNAPSHOTS is empty; nothing to build", file=sys.stderr)
        return 1

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    # selector options: newest first
    nav = []
    for i, s in enumerate(reversed(SNAPSHOTS)):
        label = pretty(s["ts"]) + (" (最新)" if i == 0 else "")
        nav.append({"ts": s["ts"], "href": f"{s['ts']}.html", "label": label})
    nav_json = json.dumps(nav, ensure_ascii=False)

    for s in SNAPSHOTS:
        src = ROOT / s["path"]
        if not src.exists():
            print(f"[skip] {src} not found", file=sys.stderr)
            continue
        out = OUT_DIR / f"{s['ts']}.html"
        cmd = [
            sys.executable,
            str(RENDERER),
            str(src),
            str(out),
            "--nav-snapshots",
            nav_json,
            "--current-ts",
            s["ts"],
        ]
        subprocess.check_call(cmd)

    latest = SNAPSHOTS[-1]
    latest_html = OUT_DIR / f"{latest['ts']}.html"
    (OUT_DIR / "index.html").write_text(
        latest_html.read_text(encoding="utf-8"), encoding="utf-8"
    )
    print(f"[ok] index.html mirrors {latest['ts']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
