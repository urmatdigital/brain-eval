# brain-eval

Grounding evaluation for a bilingual (Russian / Kyrgyz) retrieval-augmented
assistant. Data, judge and metrics behind the research proposal *Auditable
grounding for multilingual RAG in a low-resource language*, built from
[BRAIN KSTU](https://brain.kstu.kg), the production assistant of Kyrgyz State
Technical University (Bishkek).

## Why

In production we found that the assistant's "grounded" flag was degenerate:
7,616 of 7,616 logged dialogues were marked grounded, because hybrid retrieval
almost always returns a non-zero score. On 395 real questions plus 70 gold and 20
out-of-domain questions, no single score threshold separated grounded from
ungrounded answers (90% true positives retained at only 75% out-of-domain
rejection). Kyrgyz, a state language with almost no public evaluation data, is
under 2% of traffic. This repository is the open testbed for fixing that with
measurements instead of thresholds.

## What is here

| Path | Content | Licence |
|---|---|---|
| `data/orgs_ru_ky.tsv` | 722 names of Kyrgyz educational organisations, 360 Russian + 362 Kyrgyz, labelled by language. Public register entries, used as a gold set for language identification (router accuracy 64.5% → 97.9%). | CC-BY-4.0 |
| `data/goldset_admission.jsonl`, `data/goldset_hostel.jsonl` | 70 questions with expected retrieval mode and must/must-not substrings, used as the production acceptance gate. | CC-BY-4.0 |
| `data/pilot_ru_ky.schema.json` | Schema of the 200-item ru/ky pilot set (100 parallel pairs, 20 out-of-domain) with two human grounding labels and the judge label. The set itself lands here after annotation. | CC-BY-4.0 |
| `judge.py` | LLM-as-judge: labels an answer `supported` / `partial` / `unsupported` against its evidence. One prompt, one JSON schema, two providers (Anthropic SDK with structured output; OpenRouter). | Apache-2.0 |
| `kappa.py` | Cohen's κ per language with a bootstrap 95% CI, Markdown table output. | Apache-2.0 |
| `scripts/pii_scan.py` | Refuses to publish personal data: phones, e-mails, 14-digit PINs, passport ids, full names with patronymic. Runs as the gate before every commit of `data/`. | Apache-2.0 |
| `report/` | Technical report (negative result, pilot κ, study design). | CC-BY-4.0 |

## Reproduce

```sh
python -I tests/test_kappa.py                               # kappa + scanner self-check
python -I scripts/pii_scan.py data/                         # must print 0 finding(s)
python judge.py --provider anthropic --dry-run data/goldset_admission.jsonl
pip install anthropic && python judge.py --provider anthropic data/pilot_ru_ky.jsonl --runs 3 --out out/judge.jsonl
python kappa.py out/judge.jsonl
```

The judge needs `ANTHROPIC_API_KEY` (or an `ant auth login` profile) for the
`anthropic` provider and `OPENROUTER_API_KEY` for `openrouter`. Model defaults:
`claude-opus-5-5` and `deepseek/deepseek-v3.2`; override with `--model`.

## Data policy

No question, answer or evidence in this repository is copied from a real user.
Pilot questions are regenerated from topic categories of production traffic; the
production gateway itself logs topics, not texts, for its public feed. The scanner
in `scripts/pii_scan.py` is the gate, and a finding blocks the commit.

## Cite

Myrzabekov, U. (2026). *brain-eval: grounding evaluation for a Russian/Kyrgyz
retrieval-augmented university assistant.* Kyrgyz State Technical University.
https://github.com/urmatdigital/brain-eval

## Licence

Code: Apache-2.0 (`LICENSE`). Data under `data/` and the report: CC-BY-4.0
(https://creativecommons.org/licenses/by/4.0/).
