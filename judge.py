#!/usr/bin/env python3
"""Grounding judge: label an answer against its retrieved evidence.

Labels (one per item, per run):
  supported    every factual claim in the answer is backed by the evidence
  partial      some claims are backed, others are not in the evidence
  unsupported  the answer's claims are absent from or contradict the evidence

Input JSONL, one item per line:
  {"id": "...", "lang": "ru"|"ky", "question": "...", "evidence": ["..."], "answer": "..."}
Output JSONL (stdout or --out): the item plus
  {"label_judge": "...", "rationale": "...", "provider": "...", "model": "...", "run": N}

Providers:
  anthropic   official SDK, structured output (JSON schema). Env: ANTHROPIC_API_KEY
              or an `ant auth login` profile. Model: JUDGE_MODEL (default claude-opus-5-5).
  openrouter  OpenAI-compatible chat completions over urllib. Env: OPENROUTER_API_KEY,
              OPENROUTER_MODEL (default deepseek/deepseek-v3.2). Same prompt, same schema.

    python judge.py --provider anthropic data/pilot_ru_ky.jsonl --out out/judge.jsonl
    python judge.py --provider openrouter --dry-run data/goldset_admission.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request
from pathlib import Path

LABELS = ("supported", "partial", "unsupported")

# One prompt for every provider: the judge is the measurement instrument, and an
# instrument that changes with the vendor cannot be compared across vendors.
SYSTEM = (
    "You are a strict grounding auditor for a university assistant that answers in "
    "Russian and Kyrgyz. You receive a user question, the evidence passages the "
    "assistant retrieved, and the assistant's answer. Judge ONLY whether the answer's "
    "factual claims (numbers, dates, names, rules, procedures) are backed by the "
    "evidence. Do not judge style, completeness or politeness.\n"
    "- supported: every factual claim is present in the evidence (paraphrase is fine).\n"
    "- partial: at least one claim is backed and at least one is not in the evidence.\n"
    "- unsupported: the claims are absent from the evidence or contradict it, or the "
    "answer invents specifics. An answer that only says it does not know is "
    "'supported' when the evidence indeed lacks the information.\n"
    "Kyrgyz and Russian evidence may be mixed; treat a faithful translation as backed. "
    "Write the rationale in one or two sentences, in English."
)

SCHEMA = {
    "type": "object",
    "properties": {
        "label": {"type": "string", "enum": list(LABELS)},
        "rationale": {"type": "string"},
    },
    "required": ["label", "rationale"],
    "additionalProperties": False,
}


def user_message(item: dict) -> str:
    ev = "\n".join(f"[E{i + 1}] {e}" for i, e in enumerate(item.get("evidence") or []))
    return (
        f"Language: {item.get('lang', '?')}\n"
        f"Question: {item['question']}\n\n"
        f"Evidence:\n{ev or '(no evidence retrieved)'}\n\n"
        f"Answer: {item['answer']}"
    )


def _coerce(data: dict) -> dict:
    label = str(data.get("label", "")).strip().lower()
    if label not in LABELS:
        raise ValueError(f"label outside schema: {label!r}")
    return {"label": label, "rationale": str(data.get("rationale", ""))[:500]}


def judge_anthropic(item: dict, model: str) -> dict:
    import anthropic  # official SDK; install: pip install anthropic

    client = anthropic.Anthropic()
    response = client.messages.create(
        model=model,
        max_tokens=1024,
        system=SYSTEM,
        messages=[{"role": "user", "content": user_message(item)}],
        output_config={"format": {"type": "json_schema", "schema": SCHEMA}},
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"refusal: {response.stop_details}")
    text = next(b.text for b in response.content if b.type == "text")
    return _coerce(json.loads(text))


def judge_openrouter(item: dict, model: str) -> dict:
    key = os.environ.get("OPENROUTER_API_KEY", "")
    if not key:
        raise RuntimeError("OPENROUTER_API_KEY is not set")
    body = {
        "model": model,
        "temperature": 0,
        "response_format": {"type": "json_object"},
        "messages": [
            {
                "role": "system",
                "content": SYSTEM + "\nReturn ONLY a JSON object "
                '{"label": "supported|partial|unsupported", "rationale": "..."}.',
            },
            {"role": "user", "content": user_message(item)},
        ],
    }
    req = urllib.request.Request(
        "https://openrouter.ai/api/v1/chat/completions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=90) as r:
        payload = json.load(r)
    raw = payload["choices"][0]["message"]["content"]
    start, end = raw.find("{"), raw.rfind("}")
    return _coerce(json.loads(raw[start : end + 1]))


PROVIDERS = {
    "anthropic": (
        judge_anthropic,
        lambda: os.environ.get("JUDGE_MODEL", "claude-opus-5-5"),
    ),
    "openrouter": (
        judge_openrouter,
        lambda: os.environ.get("OPENROUTER_MODEL", "deepseek/deepseek-v3.2"),
    ),
}


def load(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("path", type=Path)
    ap.add_argument("--provider", choices=PROVIDERS, default="anthropic")
    ap.add_argument(
        "--model", default=None, help="override the provider's default model"
    )
    ap.add_argument(
        "--runs", type=int, default=1, help="repeat each item N times (stability)"
    )
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument(
        "--dry-run", action="store_true", help="print prompts, call nothing"
    )
    a = ap.parse_args(argv)

    fn, default_model = PROVIDERS[a.provider]
    model = a.model or default_model()
    items = load(a.path)
    # Goldset files carry "q" instead of question/answer: still useful for a dry run.
    for it in items:
        it.setdefault("question", it.get("q", ""))
        it.setdefault("answer", it.get("answer", ""))
    out = a.out.open("w", encoding="utf-8") if a.out else sys.stdout
    failures = 0
    for it in items:
        for run in range(1, a.runs + 1):
            if a.dry_run:
                print(
                    f"--- {it.get('id', '?')} run {run} ({a.provider}/{model})\n{user_message(it)}\n",
                    file=out,
                )
                continue
            try:
                verdict = fn(it, model)
            except Exception as e:  # keep going; the row records the failure
                failures += 1
                verdict = {
                    "label": None,
                    "rationale": f"ERROR {type(e).__name__}: {e}"[:300],
                }
            row = {
                **it,
                "label_judge": verdict["label"],
                "rationale": verdict["rationale"],
                "provider": a.provider,
                "model": model,
                "run": run,
            }
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
    if a.out:
        out.close()
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
