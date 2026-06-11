import re
from dataclasses import dataclass
from uuid import UUID

WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]*")
IGNORED_WORDS = {
    "a",
    "an",
    "and",
    "are",
    "as",
    "at",
    "be",
    "for",
    "in",
    "is",
    "it",
    "of",
    "on",
    "or",
    "that",
    "the",
    "to",
    "we",
    "when",
}

WRONG_THRESHOLD = 3
MASTER_THRESHOLD = 3


@dataclass(frozen=True)
class Blank:
    id: UUID
    word: str
    order_index: int


@dataclass(frozen=True)
class AnswerResult:
    blank_id: UUID
    correct: bool


def normalize_answer(value: str) -> str:
    normalized = value.strip().lower()
    normalized = normalized.replace("\u2019", "'")
    normalized = re.sub(r"^[^a-z0-9']+|[^a-z0-9']+$", "", normalized)
    return normalized


def is_answer_correct(expected: str, actual: str) -> bool:
    return normalize_answer(expected) == normalize_answer(actual)


def grade_answers(blanks: list[Blank], answers: dict[UUID, str]) -> list[AnswerResult]:
    return [
        AnswerResult(
            blank_id=blank.id,
            correct=is_answer_correct(blank.word, answers.get(blank.id, "")),
        )
        for blank in blanks
    ]


def check_answers(keywords: list[str], answers: dict[str, str]) -> dict[str, bool]:
    """Check user answers against keywords. Returns keyword -> correct."""
    results = {}
    for kw in keywords:
        user_input = answers.get(kw, "")
        results[kw] = is_answer_correct(kw, user_input)
    return results


def should_add_to_wrongbook(wrong_count: int) -> bool:
    return wrong_count >= 3


def should_mark_mastered(consecutive_correct_count: int) -> bool:
    return consecutive_correct_count >= 3


def extract_keywords(sentence: str, *, limit: int = 3) -> list[str]:
    words = WORD_RE.findall(sentence)
    keywords: list[str] = []
    seen: set[str] = set()
    for word in words:
        normalized = normalize_answer(word)
        if len(normalized) < 3 or normalized in IGNORED_WORDS or normalized in seen:
            continue
        seen.add(normalized)
        keywords.append(word)
        if len(keywords) >= limit:
            break
    return keywords


def build_group_indexes(sentence_count: int, group_size: int) -> list[range]:
    if group_size < 1:
        raise ValueError("group_size must be greater than zero")
    return [
        range(start, min(start + group_size, sentence_count))
        for start in range(0, sentence_count, group_size)
    ]
