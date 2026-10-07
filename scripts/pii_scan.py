#!/usr/bin/env python3
"""Refuse to publish personal data. Scans text files for phones, e-mails, Kyrgyz
PINs (14 digits), passport-like IDs and full personal names with a patronymic.

    python -I scripts/pii_scan.py data/            # exit 0 clean, 1 findings

Organisation names such as «лицей имени К. Осмонбекова» are public register
entries and are not personal data; the name pattern therefore requires a
patronymic or кызы/уулу, which honorific names never carry.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

PATTERNS = {
    "phone": re.compile(
        r"(?<!\d)(?:\+?996[\s-]?\d{3}[\s-]?\d{3}[\s-]?\d{3}|0\d{3}[\s-]?\d{2}[\s-]?\d{2}[\s-]?\d{2})(?!\d)"
    ),
    "email": re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+"),
    "pin14": re.compile(r"(?<!\d)[12]\d{13}(?!\d)"),
    "passport": re.compile(r"\b(?:ID|AN|AC)\s?\d{7}\b"),
    "full_name": re.compile(
        r"\b[А-ЯЁӨҮҢ][а-яёөүң]+\s+[А-ЯЁӨҮҢ][а-яёөүң]+\s+[А-ЯЁӨҮҢ][а-яёөүң]+(?:ович|евич|ич|овна|евна|ична|инична)\b"
        r"|\b[А-ЯЁӨҮҢ][а-яёөүң]+\s+[А-ЯЁӨҮҢ][а-яёөүң]+\s+(?:кызы|уулу)\b"
    ),
}

EXT = {".tsv", ".jsonl", ".json", ".md", ".txt", ".csv"}
# Role mailboxes of the university are institutional contacts, not a person's data.
ROLE_MAILBOX = re.compile(
    r"^(admission|international|online|rector|rektorat|info|priem|dekanat\.[a-z]+)@kstu\.kg$",
    re.I,
)


def scan(root: Path) -> list[str]:
    findings = []
    files = (
        [root]
        if root.is_file()
        else sorted(p for p in root.rglob("*") if p.suffix in EXT)
    )
    for p in files:
        for ln, line in enumerate(
            p.read_text(encoding="utf-8", errors="replace").splitlines(), 1
        ):
            for kind, rx in PATTERNS.items():
                for m in rx.finditer(line):
                    if kind == "email" and ROLE_MAILBOX.match(m.group(0)):
                        continue
                    findings.append(f"{p}:{ln}: {kind}: {m.group(0)}")
    return findings


def main(argv: list[str]) -> int:
    if not argv:
        print(__doc__)
        return 2
    findings = [f for a in argv for f in scan(Path(a))]
    for f in findings:
        print(f)
    print(f"{len(findings)} finding(s)")
    return 1 if findings else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
