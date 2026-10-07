# When "grounded" means nothing: measuring answer grounding in a bilingual university RAG assistant

Urmat Myrzabekov · Department of Automation, Artificial Intelligence and Robotics, Kyrgyz State Technical University named after I. Razzakov, Bishkek · draft v0.1, 2026-10-08

**Abstract.** BRAIN KSTU is a production retrieval-augmented assistant serving a 25,000-student university in Russian and Kyrgyz (~650 questions per week in October 2026). Its "grounded" flag, shown to users as a checkmark and used as the quality metric, was found to be degenerate: 7,616 of 7,616 logged dialogues carried it, because any non-zero retrieval score passed the threshold. We report (1) the measurement that exposed the defect and why raising the threshold could not fix it, (2) a 200-item Russian/Kyrgyz pilot in which two human annotators and an LLM judge label answers as supported, partial or unsupported against the exact evidence the generator saw, with Cohen's κ per language, and (3) the design of a 2,000-item study that decomposes the Kyrgyz quality gap into retrieval, extraction and generation. Data and code: https://github.com/urmatdigital/brain-eval.

## 1. System

- Corpus: curated department markdown, national regulations (НПА), vector store (Chroma, `intfloat/multilingual-e5-base`), LightRAG knowledge graph (34,023 entities on 2026-10-08).
- Pipeline: hybrid retrieval over the sources → context budget 7,000 characters → system prompt with persona and rules → generator (OpenRouter, `google/gemini-2.5-flash` in October 2026; Groq/OmniRoute for the graph) → post-filters (hostel facts guard, PII scrub).
- Traffic (7 days to 2026-10-08): 650 questions; ru 584, ky 8, en 2, zh 1.

## 2. The degenerate flag (negative result)

`is_matched(blocks)` returned `any(score > θ)` with θ = 0.0. Hybrid retrieval almost always returns at least one block with a non-zero lexical score, so the flag, and with it `confident`, `in_kstu_base` and the user-facing checkmark, were constants. On 2026-08-30, 7,616 of 7,616 rows in `kiosk_dialogs` were marked grounded. A green unit test existed; it checked that the variables were decoupled, not that the threshold could reject anything.

Raising θ was measured on 395 production questions, 70 gold questions and 20 deliberately out-of-domain questions (2026-08-23):

| θ | in-domain retained | out-of-domain rejected |
|---|---|---|
| 0.0 | 91 % | 30 % |
| 2.0 | 90 % | 75 % |
| 3.0 | 69 % | 95 % |

No threshold separated the classes, for two reasons. First, the sources score on incomparable scales (lexical heading hits in integers, cosine similarity, graph hits), and one threshold is applied to the union. Second, the same variable drove behaviour (`general_mode = not matched`), so a stricter threshold would have sent a fifth of in-domain questions to the unconstrained mode in the middle of the admission campaign. The fix shipped on 2026-08-31 split the variable (`match_theta` = 0.0 for behaviour, `grounded_theta` = 2.0 for the label), which made the label able to be negative but did not make it a measurement of grounding: it still reads retrieval scores, not the answer.

## 3. Pilot: human and LLM grounding labels (in progress)

Design. 100 Russian questions regenerated from production topic categories (80 in-domain across 11 topics, 20 out-of-domain), translated to Kyrgyz and checked by native speakers; for each question the production pipeline is run once and the evidence passages and answer are frozen (`scripts/collect_evidence.py`). Two annotators label each item `supported` / `partial` / `unsupported` after a 20-item calibration round (`report/annotation-guide.md`). An LLM judge (`judge.py`, one prompt, JSON-schema output) labels the same items three times. We report Cohen's κ with bootstrap 95 % CI for human–human and human–judge pairs, per language.

Status (2026-10-08). The 100 Russian questions have been run through the production pipeline (`data/pilot_ru.jsonl`, personal data in evidence replaced by tokens). Kyrgyz drafts exist for all 100 (`data/pilot_questions_ky_draft.jsonl`) and await native-speaker review. Human labels: not started.

First measurement, before any labelling. The production flag that replaced the degenerate one still does not measure grounding:

| questions | n | `matched` (θ = 0) | `grounded` flag (θ = 2.0) |
|---|---|---|---|
| in-domain | 80 | 80 | 78 |
| out-of-domain (weather, recipes, other universities, code) | 20 | 20 | **17** |

Seventeen of twenty questions the corpus cannot answer are marked grounded by retrieval score, while the generator itself declined all twenty correctly ("this is outside my knowledge base"). The flag and the answer disagree in opposite directions: it says the refusal is grounded, and on the fee-paying threshold question it said an answer of "110" (the grant figure; the evidence says 60 for contract places) was grounded as well. Every row carries the retrieval score and both flags, so the κ study can report how often a score-based label and an evidence-based label diverge.

Results. _Pending: table from `python kappa.py data/pilot_ru_ky.jsonl`._

## 4. Planned study (6 months)

2,000 ru/ky items; factorial ablation retriever × extractor × generator × language; knowledge-graph re-extraction with a frontier model versus the current small model, with recall on a 300-item hand-checked sample; deployment of the calibrated judge in production with an A/B on live traffic (unsupported rate, Kyrgyz share). Success criteria: κ(judge, human) ≥ 0.7 ru and ≥ 0.6 ky; out-of-domain rejection ≥ 90 % at ≥ 90 % in-domain retention; Kyrgyz share of questions doubled.

## 5. Data policy

No user text is published. Questions are regenerated from topics; the gateway's public feed logs topics, not texts. `scripts/pii_scan.py` runs before every commit of `data/` and blocks phones, e-mails, 14-digit PINs, passport ids and full personal names.

## References

_To add: RAG grounding/faithfulness evaluation (RAGAS, FActScore, ARES), LLM-as-judge agreement studies, Kyrgyz NLP resources, LightRAG._
