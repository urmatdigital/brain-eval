#!/usr/bin/env python3
"""Make a publishable copy of collected rows: personal data in evidence and answers is
replaced by stable tokens so annotators' labels still apply and the PII gate passes.

    python -I scripts/redact.py out/evidence_ru.jsonl data/pilot_ru.jsonl

Tokens: [ФИО], [PHONE], [EMAIL], [PIN], [ID]. Role mailboxes of the university
(admission@, international@, online@, rector@, dekanat.*@kstu.kg) are institutional,
not personal, and are kept. Everything else the scanner would flag is replaced.
Local, unredacted copies stay under out/ (git-ignored) for the annotators.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pii_scan import PATTERNS  # noqa: E402

ROLE_MAILBOX = re.compile(
    r"^(admission|international|online|rector|rektorat|info|priem|dekanat\.[a-z]+)@kstu\.kg$",
    re.I,
)
TOKEN = {
    "phone": "[PHONE]",
    "email": "[EMAIL]",
    "pin14": "[PIN]",
    "passport": "[ID]",
    "full_name": "[ФИО]",
}


def redact(text: str) -> tuple[str, int]:
    n = 0
    for kind, rx in PATTERNS.items():

        def sub(m: re.Match) -> str:
            nonlocal n
            if kind == "email" and ROLE_MAILBOX.match(m.group(0)):
                return m.group(0)
            n += 1
            return TOKEN[kind]

        text = rx.sub(sub, text)
    return text, n


def main(src: str, dst: str) -> int:
    total = 0
    with open(dst, "w", encoding="utf-8") as out:
        for line in open(src, encoding="utf-8"):
            if not line.strip():
                continue
            r = json.loads(line)
            r["evidence"], n1 = (
                zip(*[redact(e) for e in r.get("evidence") or []])
                if r.get("evidence")
                else ([], [0])
            )
            r["evidence"] = list(r["evidence"])
            r["answer"], n2 = redact(r.get("answer", ""))
            total += sum(n1) + n2
            out.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{total} replacements → {dst}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
