from uuid import UUID

import pytest

from listenflow.modules.practice.domain import (
    Blank,
    build_group_indexes,
    extract_keywords,
    grade_answers,
    is_answer_correct,
    normalize_answer,
    should_add_to_wrongbook,
    should_mark_mastered,
)


def test_normalize_answer_ignores_case_spaces_and_outer_punctuation() -> None:
    assert normalize_answer("  Immediate! ") == "immediate"
    assert normalize_answer("Don\u2019t") == "don't"


@pytest.mark.parametrize(
    ("expected", "actual"),
    [
        ("Immediate", "immediate"),
        ("practice", " practice "),
        ("don't", "Don\u2019t"),
    ],
)
def test_is_answer_correct(expected: str, actual: str) -> None:
    assert is_answer_correct(expected, actual)


def test_grade_answers() -> None:
    blank_id = UUID("44444444-4444-4444-8444-444444444444")
    results = grade_answers(
        [Blank(id=blank_id, word="immediate", order_index=0)],
        {blank_id: "Immediate"},
    )
    assert len(results) == 1
    assert results[0].correct


def test_wrongbook_threshold() -> None:
    assert not should_add_to_wrongbook(2)
    assert should_add_to_wrongbook(3)


def test_mastered_threshold() -> None:
    assert not should_mark_mastered(2)
    assert should_mark_mastered(3)


def test_extract_keywords_skips_stop_words_and_short_words() -> None:
    sentence = "Students learn better when practice is immediate and repeated."
    assert extract_keywords(sentence) == ["Students", "learn", "better"]


def test_build_group_indexes() -> None:
    groups = build_group_indexes(sentence_count=23, group_size=10)
    assert [list(group) for group in groups] == [
        list(range(0, 10)),
        list(range(10, 20)),
        list(range(20, 23)),
    ]


def test_build_group_indexes_rejects_invalid_size() -> None:
    with pytest.raises(ValueError, match="group_size"):
        build_group_indexes(sentence_count=10, group_size=0)
