"""LLM-backed keyword picker for listening dictation.

Given a sentence, the goal is to pick 1–5 *content* words a learner should be
forced to actually hear and type — not articles, not pronouns, not the highest
frequency function words. The naive heuristic in :mod:`practice.domain` picks
the first three non-stopword tokens, which is fine for a smoke test but bad
for learning: in *"He pointed at the painting with deliberate slowness"* it
returns ``[pointed, painting, with]`` and skips the actually-hard words.

This module batches sentences and asks Zhipu's GLM model to pick the keywords
per sentence. If no API key is configured, or the API call fails, we fall
back to the naive extractor — the pipeline stays functional offline.
"""

from __future__ import annotations

import json
import logging

import httpx

from listenflow.core.config import Settings, get_settings
from listenflow.modules.practice.domain import extract_keywords as naive_extract

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是英语听力填空练习的关键词标注助手。给定若干编号的英文句子，每句挑出 1–5 个最值得学生**听写**练习的词。

挑选原则（按优先级）：
1. 实义词（动词、名词、形容词、副词）优先
2. 中高级词汇（B2/C1 及以上）、专有名词、容易听错的词优先
3. 短语动词 / 习语里的核心词（如 "give up" 里的 give 或 up）
4. 同一个词在同一句里不要重复挑

避免：
- 冠词 (a/an/the)、介词、be 动词、助动词、代词
- 过于简单的高频词（the, is, you, have, do, go, come 等）
- 单独的数字

输出严格 JSON，键是句子编号字符串，值是关键词数组（按词在句中的出现顺序）。每个关键词必须**逐字符**出现在该句中（保留原始大小写、连字符、撇号）。

例：
输入：
1. He pointed at the painting with deliberate slowness.
2. OK.

输出：
{"1": ["pointed", "painting", "deliberate", "slowness"], "2": []}
"""


def analyze_keywords(sentences: list[str]) -> list[list[str]]:
    """Return one keyword list per input sentence, same order.

    Falls back to the naive extractor sentence-by-sentence when:
    - no Zhipu API key is configured,
    - the API call for a batch raises, or
    - the LLM returns malformed JSON / unknown sentence keys.
    """
    if not sentences:
        return []
    settings = get_settings()
    if not settings.zhipu_api_key:
        return [naive_extract(s) for s in sentences]

    results: list[list[str]] = [[] for _ in sentences]
    batch_size = settings.keyword_batch_size
    for start in range(0, len(sentences), batch_size):
        batch = sentences[start : start + batch_size]
        try:
            mapping = _call_zhipu(batch, settings)
        except Exception as exc:
            logger.warning("Zhipu keyword call failed (batch %d): %s", start, exc)
            for offset, text in enumerate(batch):
                results[start + offset] = naive_extract(text)
            continue
        for offset, text in enumerate(batch):
            picked = mapping.get(str(offset + 1), [])
            # Strict guard: every keyword must appear verbatim in the sentence.
            valid = [kw for kw in picked if isinstance(kw, str) and kw and kw in text]
            # Trim to the per-sentence cap even if the LLM ignored the prompt's "1–5".
            results[start + offset] = valid[:5] if valid else naive_extract(text)
    return results


def _call_zhipu(batch: list[str], settings: Settings) -> dict[str, list[str]]:
    numbered = "\n".join(f"{i + 1}. {text}" for i, text in enumerate(batch))
    response = httpx.post(
        f"{settings.zhipu_base_url}/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.zhipu_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": settings.zhipu_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": numbered},
            ],
            "response_format": {"type": "json_object"},
            "temperature": 0.2,
        },
        timeout=60.0,
    )
    response.raise_for_status()
    payload = response.json()
    content = payload["choices"][0]["message"]["content"]
    parsed = json.loads(content)
    if not isinstance(parsed, dict):
        raise ValueError(f"Zhipu returned non-object content: {content[:200]}")
    return parsed
