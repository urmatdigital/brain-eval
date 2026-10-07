#!/usr/bin/env python3
"""Turn collected evidence rows into an annotation sheet (TSV, opens in Numbers/Excel),
and merge filled sheets back into the pilot JSONL.

    python scripts/make_sheet.py export out/evidence_ru.jsonl out/sheet_ru.tsv
    python scripts/make_sheet.py merge  out/evidence_ru.jsonl out/sheet_ru_h1.tsv label_h1 out/sheet_ru_h2.tsv label_h2 > data/pilot_ru.jsonl

The sheet hides meta flags (matched, scores) so annotators judge text, not the system's own opinion.
"""

from __future__ import annotations

import csv
import json
import sys

LABELS = {"supported", "partial", "unsupported", ""}


def rows(path: str) -> list[dict]:
    return [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]


def export(src: str, dst: str) -> None:
    with open(dst, "w", encoding="utf-8", newline="") as fh:
        w = csv.writer(fh, delimiter="\t")
        w.writerow(["id", "question", "evidence", "answer", "label", "note"])
        for r in rows(src):
            ev = "\n\n".join(r.get("evidence") or []) or "(evidence пуст)"
            w.writerow([r["id"], r["question"], ev, r.get("answer", ""), "", ""])


def merge(src: str, pairs: list[tuple[str, str]]) -> None:
    base = {r["id"]: r for r in rows(src)}
    for sheet, col in pairs:
        with open(sheet, encoding="utf-8", newline="") as fh:
            for rec in csv.DictReader(fh, delimiter="\t"):
                label = (rec.get("label") or "").strip().lower()
                if label not in LABELS:
                    sys.exit(f"{sheet}: {rec['id']}: bad label {label!r}")
                base[rec["id"]][col] = label or None
                if rec.get("note"):
                    base[rec["id"]].setdefault("notes", {})[col] = rec["note"]
    for r in base.values():
        r.pop("meta", None)  # system flags stay out of the published set
        print(json.dumps(r, ensure_ascii=False))


if __name__ == "__main__":
    cmd, *args = sys.argv[1:]
    if cmd == "export":
        export(*args)
    elif cmd == "merge":
        src, *rest = args
        merge(src, list(zip(rest[::2], rest[1::2])))
    else:
        sys.exit(__doc__)
