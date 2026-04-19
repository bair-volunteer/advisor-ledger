#!/usr/bin/env python3
"""
Phase 1 fetcher: for each enabled source in config/source_docs.json,
pull the Google Doc via documents.get (structured JSON) and files.export
(plain text), and write timestamped snapshot files under snapshots/.

Outputs per run, per source:
  snapshots/YYYY/MM/DD/<source_id>/<ts>.json      # documents.get payload
  snapshots/YYYY/MM/DD/<source_id>/<ts>.txt       # text/plain export
  snapshots/YYYY/MM/DD/<source_id>/<ts>.meta.json # capture metadata

Auth: service account JSON at secrets/sa.json (override via env SA_JSON_PATH).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import sys
from pathlib import Path

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

ROOT = Path(__file__).resolve().parent.parent
CONFIG_PATH = ROOT / "config" / "source_docs.json"
SA_PATH = Path(os.environ.get("SA_JSON_PATH", ROOT / "secrets" / "sa.json"))
SNAPSHOTS_DIR = ROOT / "snapshots"

SCOPES = [
    "https://www.googleapis.com/auth/documents.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]


def load_config() -> list[dict]:
    cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    sources = [s for s in cfg.get("sources", []) if s.get("enabled")]
    for s in sources:
        if s["google_doc_id"].startswith("REPLACE_ME"):
            sys.exit(f"config: source '{s['source_id']}' still has a REPLACE_ME doc id")
    return sources


def build_services():
    if not SA_PATH.exists():
        sys.exit(f"service account JSON not found at {SA_PATH}")
    creds = service_account.Credentials.from_service_account_file(
        str(SA_PATH), scopes=SCOPES
    )
    docs = build("docs", "v1", credentials=creds, cache_discovery=False)
    drive = build("drive", "v3", credentials=creds, cache_discovery=False)
    return docs, drive


def prior_modified_time(source_id: str) -> str | None:
    metas = sorted(SNAPSHOTS_DIR.rglob(f"*/{source_id}/*.meta.json"))
    if not metas:
        return None
    try:
        meta = json.loads(metas[-1].read_text(encoding="utf-8"))
        return meta.get("drive_metadata", {}).get("modifiedTime")
    except Exception:
        return None


def current_modified_time(drive, doc_id: str) -> str | None:
    resp = drive.files().get(
        fileId=doc_id, fields="modifiedTime", supportsAllDrives=True
    ).execute()
    return resp.get("modifiedTime")


def fetch_one(docs, drive, source: dict, ts: str) -> Path:
    doc_id = source["google_doc_id"]
    source_id = source["source_id"]

    doc_json = docs.documents().get(documentId=doc_id).execute()
    text_bytes = drive.files().export(
        fileId=doc_id, mimeType="text/plain"
    ).execute()
    text = text_bytes.decode("utf-8", errors="replace") if isinstance(text_bytes, (bytes, bytearray)) else str(text_bytes)

    file_meta = drive.files().get(
        fileId=doc_id,
        fields="id,name,mimeType,modifiedTime,version,md5Checksum,headRevisionId",
        supportsAllDrives=True,
    ).execute()

    out_dir = SNAPSHOTS_DIR / ts[:4] / ts[5:7] / ts[8:10] / source_id
    out_dir.mkdir(parents=True, exist_ok=True)

    json_path = out_dir / f"{ts}.json"
    txt_path = out_dir / f"{ts}.txt"
    meta_path = out_dir / f"{ts}.meta.json"

    json_path.write_text(
        json.dumps(doc_json, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    txt_path.write_text(text, encoding="utf-8")

    meta = {
        "source_id": source_id,
        "source_name": source.get("name"),
        "google_doc_id": doc_id,
        "captured_at_utc": ts,
        "drive_metadata": file_meta,
        "text_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
        "text_byte_len": len(text.encode("utf-8")),
        "doc_json_sha256": hashlib.sha256(
            json.dumps(doc_json, ensure_ascii=False, sort_keys=True).encode("utf-8")
        ).hexdigest(),
    }
    meta_path.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    return out_dir


def main() -> int:
    sources = load_config()
    if not sources:
        print("no enabled sources in config; nothing to do", file=sys.stderr)
        return 0

    docs, drive = build_services()
    ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")

    exit_code = 0
    for source in sources:
        try:
            prior = prior_modified_time(source["source_id"])
            current = current_modified_time(drive, source["google_doc_id"])
            if prior is not None and current is not None and prior == current:
                print(
                    f"[{source['source_id']}] unchanged (modifiedTime={current}), skipping"
                )
                continue
            out_dir = fetch_one(docs, drive, source, ts)
            print(f"[{source['source_id']}] wrote snapshot to {out_dir}/{ts}.*")
        except HttpError as e:
            print(f"[{source['source_id']}] Google API error: {e}", file=sys.stderr)
            exit_code = 1
        except Exception as e:
            print(f"[{source['source_id']}] failed: {e!r}", file=sys.stderr)
            exit_code = 1
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
