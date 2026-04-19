#!/usr/bin/env python3
"""
Phase 2 normalizer: read a documents.get snapshot (.json) and produce a
deterministic, diff-friendly representation.

Output: normalized/YYYY/MM/DD/<source_id>/<ts>.normalized.json

{
  "source_id", "google_doc_id", "captured_at_utc", "title", "revision_id",
  "paragraphs": [
    {"index": 0, "content_hash": "<16 hex>", "style": "NORMAL_TEXT", "text": "..."},
    ...
  ],
  "skipped": {"sectionBreak": 1, "table": 0, ...}
}

Usage:
  normalize_doc.py <snapshot.json>              # write alongside in normalized/
  normalize_doc.py --all                        # normalize every snapshot that
                                                # doesn't yet have a normalized/ twin
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SNAPSHOTS_DIR = ROOT / "snapshots"
NORMALIZED_DIR = ROOT / "normalized"


def extract_paragraph_text(paragraph: dict) -> str:
    parts: list[str] = []
    for el in paragraph.get("elements", []):
        tr = el.get("textRun")
        if tr and "content" in tr:
            parts.append(tr["content"])
    return "".join(parts)


def normalize_text(raw: str) -> str:
    # NFC-normalize, strip BOM, drop trailing \n per line, rstrip whole string.
    s = unicodedata.normalize("NFC", raw)
    s = s.lstrip("\ufeff")
    lines = [ln.rstrip() for ln in s.split("\n")]
    # drop trailing empty lines inside the paragraph block
    while lines and lines[-1] == "":
        lines.pop()
    return "\n".join(lines)


def normalize_doc_json(doc: dict, meta: dict) -> dict:
    paragraphs: list[dict] = []
    skipped: dict[str, int] = {}
    for el in doc.get("body", {}).get("content", []):
        kinds = [k for k in el.keys() if k not in ("startIndex", "endIndex")]
        if "paragraph" in kinds:
            raw = extract_paragraph_text(el["paragraph"])
            text = normalize_text(raw)
            if text == "":
                # preserve blank paragraphs; they're meaningful for structure
                # but use a fixed sentinel hash so many blanks don't cost hash cycles
                content_hash = "0" * 16
            else:
                content_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
            style = (
                el["paragraph"]
                .get("paragraphStyle", {})
                .get("namedStyleType", "NORMAL_TEXT")
            )
            paragraphs.append(
                {
                    "index": len(paragraphs),
                    "content_hash": content_hash,
                    "style": style,
                    "text": text,
                }
            )
        else:
            for k in kinds:
                skipped[k] = skipped.get(k, 0) + 1

    return {
        "source_id": meta["source_id"],
        "google_doc_id": meta["google_doc_id"],
        "captured_at_utc": meta["captured_at_utc"],
        "title": doc.get("title"),
        "revision_id": doc.get("revisionId"),
        "paragraph_count": len(paragraphs),
        "paragraphs": paragraphs,
        "skipped": skipped,
    }


def paths_for_snapshot(snapshot_json_path: Path) -> tuple[Path, Path]:
    # snapshots/YYYY/MM/DD/<source_id>/<ts>.json
    # -> normalized/YYYY/MM/DD/<source_id>/<ts>.normalized.json
    rel = snapshot_json_path.relative_to(SNAPSHOTS_DIR)
    out = NORMALIZED_DIR / rel.with_suffix("").with_suffix(".normalized.json")
    meta = snapshot_json_path.with_suffix(".meta.json").with_name(
        snapshot_json_path.stem + ".meta.json"
    )
    return out, meta


def normalize_one(snapshot_json_path: Path) -> Path:
    out_path, meta_path = paths_for_snapshot(snapshot_json_path)
    doc = json.loads(snapshot_json_path.read_text(encoding="utf-8"))
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    normalized = normalize_doc_json(doc, meta)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return out_path


def iter_all_snapshots() -> list[Path]:
    return sorted(
        p
        for p in SNAPSHOTS_DIR.rglob("*.json")
        if not p.name.endswith(".meta.json")
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("snapshot", nargs="?", help="path to a snapshot .json")
    ap.add_argument("--all", action="store_true", help="normalize every snapshot")
    ap.add_argument(
        "--force", action="store_true", help="re-normalize even if output exists"
    )
    args = ap.parse_args()

    if args.all:
        targets = iter_all_snapshots()
    elif args.snapshot:
        targets = [Path(args.snapshot).resolve()]
    else:
        ap.error("provide a snapshot path or --all")

    exit_code = 0
    for snap in targets:
        try:
            out_path, _ = paths_for_snapshot(snap)
            if out_path.exists() and not args.force:
                print(f"[skip] {out_path.relative_to(ROOT)} exists")
                continue
            written = normalize_one(snap)
            print(f"[ok] {snap.relative_to(ROOT)} -> {written.relative_to(ROOT)}")
        except Exception as e:
            print(f"[err] {snap}: {e!r}", file=sys.stderr)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
