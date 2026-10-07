#!/usr/bin/env python3
"""Draft Kyrgyz versions of the Russian pilot questions for native-speaker review.

Runs inside the brain-gateway container (uses its LLM provider):

    docker exec brain-gateway python /tmp/translate_ky.py /tmp/q100.jsonl /tmp/ky_draft.jsonl

Output rows: {"id": "ky-001", "lang": "ky", "pair": "ru-001", "topic", "ood",
"question_ru", "question": <draft>, "review": "pending"}. A draft is NOT data until a
native speaker sets review to "ok" or rewrites the question (see annotation-guide).
"""

from __future__ import annotations

import asyncio
import json
import sys

sys.path.insert(0, "/app")
import llm  # noqa: E402

SYSTEM = (
    "Сен кыргыз тилинин адисисиң. Берилген суроону орус тилинен кыргыз тилине "
    "котор. Абитуриент же студент жазгандай, жөнөкөй, жандуу тил менен жаз; "
    "расмий-китептик стилден качып, кадимки сүйлөшүү формасын колдон. Сандарды, "
    "аталыштарды (КГТУ, ОРТ, PhD) өзгөртпө. Жооп катары суроонун өзүн гана кайтар, "
    "башка эч нерсе жазба."
)


async def main(src: str, dst: str) -> int:
    items = [json.loads(l) for l in open(src, encoding="utf-8") if l.strip()]
    model = llm.resolve_model(None)
    failures = 0
    with open(dst, "w", encoding="utf-8") as out:
        for i, it in enumerate(items, 1):
            try:
                ky = (
                    (
                        await llm.chat(
                            [
                                {"role": "system", "content": SYSTEM},
                                {"role": "user", "content": it["question"]},
                            ],
                            model=model,
                            max_tokens=200,
                        )
                    )
                    .strip()
                    .strip('"«»')
                )
            except Exception as e:
                failures += 1
                ky = f"ERROR {type(e).__name__}: {e}"[:200]
            row = {
                "id": it["id"].replace("ru-", "ky-"),
                "lang": "ky",
                "pair": it["id"],
                "topic": it["topic"],
                "ood": it["ood"],
                "question_ru": it["question"],
                "question": ky,
                "review": "pending",
                "model": model,
            }
            out.write(json.dumps(row, ensure_ascii=False) + "\n")
            out.flush()
            print(f"{i}/{len(items)} {row['id']}", file=sys.stderr)
    return failures


if __name__ == "__main__":
    sys.exit(1 if asyncio.run(main(sys.argv[1], sys.argv[2])) else 0)
