#!/usr/bin/env python3
"""Run pilot questions through the production RAG pipeline and record, per question,
exactly the evidence the generator saw and the answer it produced.

Runs INSIDE the brain-gateway container (needs its modules and provider keys):

    docker cp scripts/collect_evidence.py brain-gateway:/tmp/
    docker cp data/pilot_questions_ru.jsonl brain-gateway:/tmp/q.jsonl
    docker exec brain-gateway python /tmp/collect_evidence.py /tmp/q.jsonl /tmp/out.jsonl
    docker cp brain-gateway:/tmp/out.jsonl out/evidence_ru.jsonl

Replicates `main._run_chat` lines retrieve → _build_system → llm.chat → hostel guard,
without the answer cache, cost counter, chat-actions and logging, so nothing is
written to production tables. Blocks are stored as the generator saw them
(`knowledge.build_context` order and truncation), one string per block.
"""

from __future__ import annotations

import asyncio
import json
import sys

sys.path.insert(0, "/app")

import answer_guard  # noqa: E402
import kioskconfig  # noqa: E402
import knowledge  # noqa: E402
import llm  # noqa: E402
import main  # noqa: E402  (imports the FastAPI app; lifespan does not run)
import pii  # noqa: E402


def evidence_strings(blocks: list[dict], max_chars: int | None) -> list[str]:
    """Same selection and truncation as knowledge.build_context, kept as a list."""
    ctx = knowledge.build_context(blocks, max_chars=max_chars)
    return [p for p in ctx.split("\n\n<<< ") if p.strip()] if ctx else []


async def one(item: dict, scope: str) -> dict:
    q = item["question"]
    lang = item.get("lang", "")
    blocks = knowledge.hybrid_retrieve(q, role="anonymous", scope=scope)
    matched = knowledge.is_matched(blocks)
    grounded = knowledge.is_grounded(blocks)
    system, matched2, price_intent, web_results, web_mode, general_mode = (
        main._build_system(
            q,
            blocks,
            matched,
            role="anonymous",
            tenant_id=None,
            brand_l="",
            lang_l=lang,
        )
    )
    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": pii.scrub(q)},
    ]
    model = llm.resolve_model(None)
    answer = await llm.chat(messages, model=model)
    try:
        answer, _ = answer_guard.guard_hostel(q, answer, system)
    except Exception:
        pass
    max_chars = knowledge.PRICE_CONTEXT_CHARS if price_intent else None
    return {
        **item,
        "evidence": evidence_strings(blocks, max_chars),
        "answer": answer,
        "config": "baseline",
        "meta": {
            "model": model,
            "matched": bool(matched2),
            "grounded_theta_flag": bool(grounded),
            "top_score": max((b.get("score", 0.0) for b in blocks), default=0.0),
            "n_blocks": len(blocks),
            "source_mode": "web"
            if web_mode
            else ("general_llm" if general_mode else "kgtu_base"),
            "price_intent": bool(price_intent),
        },
    }


async def run(src: str, dst: str) -> int:
    scope = kioskconfig.get("scope")
    items = [json.loads(l) for l in open(src, encoding="utf-8") if l.strip()]
    failures = 0
    with open(dst, "w", encoding="utf-8") as out:
        for i, item in enumerate(items, 1):
            try:
                row = await one(item, scope)
            except Exception as e:  # record and continue; the row says why
                failures += 1
                row = {
                    **item,
                    "evidence": [],
                    "answer": "",
                    "config": "baseline",
                    "meta": {"error": f"{type(e).__name__}: {e}"[:300]},
                }
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            print(
                f"{i}/{len(items)} {item['id']} {row['meta'].get('source_mode', 'ERR')}",
                file=sys.stderr,
            )
    return failures


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(run(sys.argv[1], sys.argv[2])) else 0)
