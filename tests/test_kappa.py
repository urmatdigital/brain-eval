"""Smallest check that fails if kappa or the scanner break. Run: python -I tests/test_kappa.py"""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from kappa import cohen_kappa, pairs  # noqa: E402

rows = [
    json.loads(l)
    for l in (ROOT / "tests/fixtures/kappa_toy.jsonl").read_text().splitlines()
    if l.strip()
]
a, b, skipped = pairs(rows, "label_h1", "label_h2")
# Fixture by hand: po = 8/10, h1 marginals 6/4, h2 marginals 6/4 → pe = 0.52 → κ = 0.28/0.48.
assert skipped == 1, skipped
assert abs(cohen_kappa(a, b) - 0.28 / 0.48) < 1e-9, cohen_kappa(a, b)
assert cohen_kappa(["x"] * 5, ["x"] * 5) == 1.0
assert cohen_kappa(["x", "y"], ["y", "x"]) == -1.0

# PII scanner: a planted phone and a full name must be caught; an honorific org name must not.
bad = ROOT / "tests/fixtures/_pii_bad.txt"
bad.write_text(
    "звоните +996 555 123 456\nМырзабеков Урмат Мырзабекович\n", encoding="utf-8"
)
good = ROOT / "tests/fixtures/_pii_good.txt"
good.write_text(
    "ПРОФЕССИОНАЛЬНЫЙ ЛИЦЕЙ №41 имени К. ОСМОНБЕКОВА\nОШ МАМЛЕКЕТТИК УНИВЕРСИТЕТИ\n",
    encoding="utf-8",
)
try:
    r_bad = subprocess.run(
        [sys.executable, "-I", "scripts/pii_scan.py", str(bad)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    r_good = subprocess.run(
        [sys.executable, "-I", "scripts/pii_scan.py", str(good)],
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
finally:
    bad.unlink()
    good.unlink()
assert (
    r_bad.returncode == 1 and "phone" in r_bad.stdout and "full_name" in r_bad.stdout
), r_bad.stdout
assert r_good.returncode == 0, r_good.stdout
print("ok")
