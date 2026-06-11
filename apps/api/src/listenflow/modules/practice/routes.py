"""Practice routes - real database-backed practice session."""

from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from listenflow.db import get_db
from listenflow.models import (
    Favorite,
    PracticeAttempt,
    Progress,
    Sentence,
    User,
    WrongRecord,
)
from listenflow.modules.practice.domain import (
    WRONG_THRESHOLD,
    check_answers,
)

router = APIRouter(prefix="/api/practice", tags=["practice"])

DEFAULT_USER_ID = "default"  # MVP: single user


def _ensure_user(db: Session) -> User:
    user = db.scalar(select(User).where(User.username == "default"))
    if not user:
        user = User(id=DEFAULT_USER_ID, username="default")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


# ── Schemas ────────────────────────────────────────────────────────────


class SentenceOut(BaseModel):
    id: str
    text: str
    display_text: str  # text with keywords blanked
    keywords: list[str]
    group_index: int
    sentence_index: int
    audio_path: str | None
    start_time: float
    end_time: float
    is_favorite: bool = False
    wrong_count: int = 0

    model_config = {"from_attributes": True}


class GroupOut(BaseModel):
    material_id: str
    group_index: int
    total_sentences: int
    sentences: list[SentenceOut]


class SubmitRequest(BaseModel):
    sentence_id: str
    answers: dict[str, str]  # keyword -> user_input


class SubmitResult(BaseModel):
    sentence_id: str
    results: dict[str, bool]  # keyword -> correct
    all_correct: bool
    wrong_count_total: int
    added_to_wrongbook: bool


class ProgressOut(BaseModel):
    material_id: str
    group_index: int
    sentence_index: int


class ContinueResponse(BaseModel):
    progress: ProgressOut
    group: GroupOut


# ── Continue (resume last position) ────────────────────────────────────


@router.get("/continue/{material_id}", response_model=ContinueResponse)
def continue_practice(material_id: str, db: Annotated[Session, Depends(get_db)]):
    user = _ensure_user(db)

    # Get progress
    progress = db.scalar(
        select(Progress).where(
            Progress.user_id == user.id, Progress.material_id == material_id
        )
    )
    if not progress:
        # Start from group 0, sentence 0
        progress = Progress(
            id=__import__("uuid").uuid4().hex,
            user_id=user.id,
            material_id=material_id,
            group_index=0,
            sentence_index=0,
        )
        db.add(progress)
        db.commit()
        db.refresh(progress)

    # Load group
    group = _load_group(db, user.id, material_id, progress.group_index)
    if not group:
        raise HTTPException(404, "No sentences found for this material")
    return ContinueResponse(
        progress=ProgressOut(
            material_id=material_id,
            group_index=progress.group_index,
            sentence_index=progress.sentence_index,
        ),
        group=group,
    )


# ── Get group ──────────────────────────────────────────────────────────


@router.get("/group/{material_id}/{group_index}", response_model=GroupOut)
def get_group(
    material_id: str, group_index: int, db: Annotated[Session, Depends(get_db)]
):
    user = _ensure_user(db)
    group = _load_group(db, user.id, material_id, group_index)
    if not group:
        raise HTTPException(404, "Group not found")
    return group


# ── Submit answer ──────────────────────────────────────────────────────


@router.post("/submit", response_model=SubmitResult)
def submit_answer(req: SubmitRequest, db: Annotated[Session, Depends(get_db)]):
    import uuid

    user = _ensure_user(db)
    sentence = db.scalar(select(Sentence).where(Sentence.id == req.sentence_id))
    if not sentence:
        raise HTTPException(404, "Sentence not found")

    keywords: list[str] = json.loads(sentence.keywords)
    results = check_answers(keywords, req.answers)
    all_correct = all(results.values())

    # Record attempt
    attempt = PracticeAttempt(
        id=uuid.uuid4().hex,
        user_id=user.id,
        sentence_id=sentence.id,
        is_correct=all_correct,
        user_input=json.dumps(req.answers),
    )
    db.add(attempt)

    # Update wrong record
    wrong_count = 0
    added_to_wrongbook = False
    if not all_correct:
        wrong_record = db.scalar(
            select(WrongRecord).where(
                WrongRecord.user_id == user.id,
                WrongRecord.sentence_id == sentence.id,
            )
        )
        if wrong_record:
            wrong_record.wrong_count += 1
            wrong_count = wrong_record.wrong_count
        else:
            wrong_record = WrongRecord(
                id=uuid.uuid4().hex,
                user_id=user.id,
                sentence_id=sentence.id,
                wrong_count=1,
                mastered=False,
            )
            db.add(wrong_record)
            wrong_count = 1

        if wrong_count >= WRONG_THRESHOLD:
            added_to_wrongbook = True

    # If all correct, update progress
    if all_correct:
        next_idx = sentence.sentence_index + 1
        progress = db.scalar(
            select(Progress).where(
                Progress.user_id == user.id,
                Progress.material_id == sentence.material_id,
            )
        )
        if progress and next_idx > progress.sentence_index:
            progress.sentence_index = next_idx
            # Check if we need to move to next group
            group_count = db.scalar(
                select(func.count())
                .select_from(Sentence)
                .where(
                    Sentence.material_id == sentence.material_id,
                    Sentence.group_index == sentence.group_index,
                )
            )
            if next_idx >= (group_count or 10):
                progress.group_index += 1
                progress.sentence_index = 0

    db.commit()

    return SubmitResult(
        sentence_id=sentence.id,
        results=results,
        all_correct=all_correct,
        wrong_count_total=wrong_count,
        added_to_wrongbook=added_to_wrongbook,
    )


# ── Favorite ───────────────────────────────────────────────────────────


@router.post("/favorite/{sentence_id}", status_code=201)
def add_favorite(sentence_id: str, db: Annotated[Session, Depends(get_db)]):
    import uuid

    user = _ensure_user(db)
    exists = db.scalar(
        select(Favorite).where(
            Favorite.user_id == user.id, Favorite.sentence_id == sentence_id
        )
    )
    if exists:
        return {"status": "already_favorited"}
    fav = Favorite(id=uuid.uuid4().hex, user_id=user.id, sentence_id=sentence_id)
    db.add(fav)
    db.commit()
    return {"status": "favorited"}


@router.delete("/favorite/{sentence_id}")
def remove_favorite(sentence_id: str, db: Annotated[Session, Depends(get_db)]):
    user = _ensure_user(db)
    fav = db.scalar(
        select(Favorite).where(
            Favorite.user_id == user.id, Favorite.sentence_id == sentence_id
        )
    )
    if fav:
        db.delete(fav)
        db.commit()
    return {"status": "removed"}


# ── Wrongbook ──────────────────────────────────────────────────────────


@router.get("/wrongbook", response_model=list[SentenceOut])
def get_wrongbook(db: Annotated[Session, Depends(get_db)]):
    user = _ensure_user(db)
    records = db.scalars(
        select(WrongRecord)
        .where(WrongRecord.user_id == user.id, WrongRecord.mastered == False)  # noqa: E712
        .order_by(WrongRecord.updated_at.desc())
    ).all()

    result = []
    for r in records:
        s = r.sentence
        kws: list[str] = json.loads(s.keywords)
        result.append(
            SentenceOut(
                id=s.id,
                text=s.text,
                display_text=_blank_keywords(s.text, kws),
                keywords=kws,
                group_index=s.group_index,
                sentence_index=s.sentence_index,
                audio_path=s.audio_path,
                start_time=s.start_time,
                end_time=s.end_time,
                is_favorite=True,
                wrong_count=r.wrong_count,
            )
        )
    return result


# ── Favorites list ─────────────────────────────────────────────────────


@router.get("/favorites", response_model=list[SentenceOut])
def get_favorites(db: Annotated[Session, Depends(get_db)]):
    user = _ensure_user(db)
    favs = db.scalars(
        select(Favorite)
        .where(Favorite.user_id == user.id)
        .order_by(Favorite.created_at.desc())
    ).all()

    result = []
    for f in favs:
        s = f.sentence
        kws: list[str] = json.loads(s.keywords)
        result.append(
            SentenceOut(
                id=s.id,
                text=s.text,
                display_text=_blank_keywords(s.text, kws),
                keywords=kws,
                group_index=s.group_index,
                sentence_index=s.sentence_index,
                audio_path=s.audio_path,
                start_time=s.start_time,
                end_time=s.end_time,
                is_favorite=True,
                wrong_count=0,
            )
        )
    return result


# ── Helpers ────────────────────────────────────────────────────────────


def _blank_keywords(text: str, keywords: list[str]) -> str:
    display = text
    for kw in keywords:
        display = display.replace(kw, "____", 1)
    return display


def _load_group(
    db: Session, user_id: str, material_id: str, group_index: int
) -> GroupOut | None:
    sentences = db.scalars(
        select(Sentence)
        .where(Sentence.material_id == material_id, Sentence.group_index == group_index)
        .order_by(Sentence.sentence_index)
    ).all()

    if not sentences:
        return None

    # Get favorites and wrong records for this user
    fav_ids = set(
        db.scalars(
            select(Favorite.sentence_id).where(Favorite.user_id == user_id)
        ).all()
    )
    wrong_map = dict(
        db.execute(
            select(WrongRecord.sentence_id, WrongRecord.wrong_count).where(
                WrongRecord.user_id == user_id,
                WrongRecord.mastered == False,  # noqa: E712
            )
        ).all()
    )

    sentence_outs = []
    for s in sentences:
        kws: list[str] = json.loads(s.keywords)
        sentence_outs.append(
            SentenceOut(
                id=s.id,
                text=s.text,
                display_text=_blank_keywords(s.text, kws),
                keywords=kws,
                group_index=s.group_index,
                sentence_index=s.sentence_index,
                audio_path=s.audio_path,
                start_time=s.start_time,
                end_time=s.end_time,
                is_favorite=s.id in fav_ids,
                wrong_count=wrong_map.get(s.id, 0),
            )
        )

    return GroupOut(
        material_id=material_id,
        group_index=group_index,
        total_sentences=len(sentence_outs),
        sentences=sentence_outs,
    )
