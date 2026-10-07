#!/usr/bin/env python3
"""Cohen's kappa between two label columns, per language, with a bootstrap CI.

    python kappa.py data/pilot_ru_ky.jsonl                      # h1 vs h2, h1 vs judge, h2 vs judge
    python kappa.py data/pilot_ru_ky.jsonl --a label_h1 --b label_judge

Rows without both labels are skipped and counted. Output is a Markdown table so it
pastes into the report unchanged.
"""

from __future__ import annotations

import argparse
import json
import random
from collections import Counter
from pathlib import Path


def cohen_kappa(a: list, b: list) -> float:
    """Plain (unweighted) Cohen's kappa. Returns 1.0 when both raters are constant and agree."""
    n = len(a)
    if n == 0:
        raise ValueError("no pairs")
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = Counter(a), Counter(b)
    pe = sum(ca[k] * cb[k] for k in set(a) | set(b)) / (n * n)
    if pe == 1.0:
        return 1.0
    return (po - pe) / (1 - pe)


def bootstrap_ci(
    a: list, b: list, iters: int = 2000, seed: int = 0
) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(a)
    ks = []
    for _ in range(iters):
        idx = [rng.randrange(n) for _ in range(n)]
        ks.append(cohen_kappa([a[i] for i in idx], [b[i] for i in idx]))
    ks.sort()
    return ks[int(0.025 * iters)], ks[int(0.975 * iters)]


def pairs(rows: list[dict], ca: str, cb: str) -> tuple[list, list, int]:
    a, b, skipped = [], [], 0
    for r in rows:
        if r.get(ca) is None or r.get(cb) is None:
            skipped += 1
            continue
        a.append(r[ca])
        b.append(r[cb])
    return a, b, skipped


def table(rows: list[dict], combos: list[tuple[str, str]], iters: int) -> str:
    langs = sorted({r.get("lang", "?") for r in rows})
    lines = [
        "| pair | lang | n | skipped | kappa | 95% CI |",
        "|---|---|---:|---:|---:|---|",
    ]
    for ca, cb in combos:
        for lang in ["all", *langs]:
            sub = rows if lang == "all" else [r for r in rows if r.get("lang") == lang]
            a, b, skipped = pairs(sub, ca, cb)
            if len(a) < 2:
                lines.append(
                    f"| {ca} vs {cb} | {lang} | {len(a)} | {skipped} | — | — |"
                )
                continue
            k = cohen_kappa(a, b)
            lo, hi = bootstrap_ci(a, b, iters)
            lines.append(
                f"| {ca} vs {cb} | {lang} | {len(a)} | {skipped} | {k:.3f} | [{lo:.3f}, {hi:.3f}] |"
            )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("path", type=Path)
    ap.add_argument("--a", default=None)
    ap.add_argument("--b", default=None)
    ap.add_argument("--iters", type=int, default=2000)
    args = ap.parse_args(argv)
    with args.path.open(encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    if args.a and args.b:
        combos = [(args.a, args.b)]
    else:
        combos = [
            ("label_h1", "label_h2"),
            ("label_h1", "label_judge"),
            ("label_h2", "label_judge"),
        ]
    print(table(rows, combos, args.iters))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
