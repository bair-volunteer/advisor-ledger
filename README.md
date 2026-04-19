# Advisor Ledger

Append-only mirror of the community-maintained "学术黑榜 / Advisor Red Flags Notes" Google Doc, with every edit tracked and every deletion preserved.

**Live rendered view**: https://the-hidden-fish.github.io/advisor-ledger/

## What and why

The source doc is anonymously editable, which means substantive observations can be quietly removed. This repository captures the doc every few minutes and commits the result to git, so the edit history — including retracted or overwritten content — stays visible.

Each commit in `main` corresponds to one real change to the source doc.

## Layout

| Path | Purpose |
|---|---|
| `snapshots/YYYY/MM/DD/<source>/*.json` | Full `documents.get` JSON per capture |
| `snapshots/.../*.txt` | Plain-text export |
| `snapshots/.../*.meta.json` | Drive metadata + SHA-256 of the capture |
| `deltas/.../*.delta.json` | Structured diff against the previous snapshot (insert / delete / replace per paragraph) |
| `reviews/.../*.review.json` | Per-delta LLM audit; flags potential PII, personal attacks, or suspicious deletions. **Advisory only** — never blocks a commit |
| `docs/index.html` | Rendered view: current text with deleted paragraphs preserved in-place (strikethrough + deletion timestamp), additions highlighted. Served by GitHub Pages. |
| `scripts/` | Pipeline: fetch → normalize → diff → review → render → commit → push |

## Pipeline

Runs every 2 minutes via a systemd timer.

1. Query Drive for the doc's `modifiedTime`. If unchanged since the last snapshot, exit early.
2. Fetch the structured JSON and plain-text export.
3. Normalize paragraphs into a deterministic, diff-friendly form (NFC unicode, line-level rstrip, content-hash per paragraph).
4. Diff the new normalized snapshot against the previous one, emitting operations keyed to paragraph content hashes so genuinely-unchanged paragraphs don't show up as churn.
5. Run a local LLM review over the delta, flagging three things: PII about private individuals, pure personal attacks (not criticism of specific behavior), and suspicious deletions that look like suppression of substantive observations. The review is written as a JSON artifact alongside the delta.
6. Re-render `docs/index.html` — current text plus preserved ghost paragraphs anchored near their last-known position.
7. `git add` the new snapshot, delta, review, and rendered site; commit and push.

A `flock` on the pipeline prevents a manual invocation and a timer-triggered run from racing on git.

## About the source

This repo is an **observational mirror**. It is not produced, endorsed, or moderated by any party named in the source document. Content in `snapshots/` and `docs/` belongs to its original anonymous contributors. To add, correct, or retract something, edit the source Google Doc directly — this repo only observes.

## License

Pipeline code (`scripts/`) is released into the public domain (CC0). The mirrored content in `snapshots/`, `deltas/`, and `docs/` retains its original authors' rights.
