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
    JobStatus,
    Material,
    MediaJob,
    PracticeAttempt,
    Progress,
    Sentence,
    Stage,
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


class RecentOut(BaseModel):
    material_id: str


@router.get("/recent", response_model=RecentOut)
def recent_material(db: Annotated[Session, Depends(get_db)]) -> RecentOut:
    """Material the user practiced most recently.

    Falls back to the newest done material when there's no prior progress,
    so a freshly-installed user clicking "继续学习" still lands on something
    playable instead of an error page.
    """
    user = _ensure_user(db)
    recent = db.scalar(
        select(Progress.material_id)
        .where(Progress.user_id == user.id)
        .order_by(Progress.updated_at.desc())
        .limit(1)
    )
    if recent:
        return RecentOut(material_id=recent)

    fallback = db.scalar(
        select(Material.id)
        .join(MediaJob, MediaJob.material_id == Material.id)
        .where(MediaJob.status == JobStatus.DONE)
        .order_by(Material.created_at.desc())
        .limit(1)
    )
    if fallback:
        return RecentOut(material_id=fallback)
    raise HTTPException(404, "No practiceable material yet")


# ── Stages (关卡) ──────────────────────────────────────────────────────


class StageOut(BaseModel):
    group_index: int
    sentence_count: int
    stars: int
    best_accuracy: float
    attempts: int


class StagesResponse(BaseModel):
    material_id: str
    stages: list[StageOut]


class CompleteStageRequest(BaseModel):
    correct_count: int
    total_count: int


def _accuracy_to_stars(accuracy: float) -> int:
    """≥95% → 3 stars, ≥80% → 2 stars, >0% (i.e. completed) → 1 star."""
    if accuracy >= 95:
        return 3
    if accuracy >= 80:
        return 2
    return 1


@router.get("/stages/{material_id}", response_model=StagesResponse)
def get_stages(
    material_id: str, db: Annotated[Session, Depends(get_db)]
) -> StagesResponse:
    """List every group of this material with the user's best stage record.

    Groups that have never been attempted are still listed (stars=0,
    best_accuracy=0, attempts=0) so the UI can show locked-but-visible cards.
    """
    user = _ensure_user(db)

    # Count sentences per group_index.
    counts: dict[int, int] = {
        int(group_index): int(count)
        for group_index, count in db.execute(
            select(Sentence.group_index, func.count(Sentence.id))
            .where(Sentence.material_id == material_id)
            .group_by(Sentence.group_index)
            .order_by(Sentence.group_index)
        ).all()
    }
    if not counts:
        return StagesResponse(material_id=material_id, stages=[])

    # Pull existing stage records (one per (user, material, group)).
    records: dict[int, Stage] = {
        s.group_index: s
        for s in db.scalars(
            select(Stage).where(
                Stage.user_id == user.id, Stage.material_id == material_id
            )
        ).all()
    }

    out: list[StageOut] = []
    for group_index in sorted(counts):
        rec = records.get(group_index)
        out.append(
            StageOut(
                group_index=group_index,
                sentence_count=counts[group_index],
                stars=rec.stars if rec else 0,
                best_accuracy=rec.best_accuracy if rec else 0.0,
                attempts=rec.attempts if rec else 0,
            )
        )
    return StagesResponse(material_id=material_id, stages=out)


@router.post(
    "/stages/{material_id}/{group_index}/complete", response_model=StageOut
)
def complete_stage(
    material_id: str,
    group_index: int,
    req: CompleteStageRequest,
    db: Annotated[Session, Depends(get_db)],
) -> StageOut:
    """Record an attempt result and bump best_accuracy / stars accordingly."""
    if req.total_count <= 0:
        raise HTTPException(400, "total_count must be > 0")
    if req.correct_count < 0 or req.correct_count > req.total_count:
        raise HTTPException(400, "correct_count out of range")

    user = _ensure_user(db)
    accuracy = (req.correct_count / req.total_count) * 100.0
    this_stars = _accuracy_to_stars(accuracy)

    stage = db.scalar(
        select(Stage).where(
            Stage.user_id == user.id,
            Stage.material_id == material_id,
            Stage.group_index == group_index,
        )
    )
    if stage is None:
        stage = Stage(
            user_id=user.id,
            material_id=material_id,
            group_index=group_index,
            stars=this_stars,
            best_accuracy=accuracy,
            attempts=1,
            completed_at=func.now(),
        )
        db.add(stage)
    else:
        stage.attempts += 1
        if accuracy > stage.best_accuracy:
            stage.best_accuracy = accuracy
        if this_stars > stage.stars:
            stage.stars = this_stars
        if stage.completed_at is None:
            stage.completed_at = func.now()
    db.commit()
    db.refresh(stage)

    # Need the group's sentence count for the response so the UI doesn't
    # have to round-trip back to /stages just to redraw one card.
    sentence_count = int(
        db.scalar(
            select(func.count(Sentence.id)).where(
                Sentence.material_id == material_id,
                Sentence.group_index == group_index,
            )
        )
        or 0
    )
    return StageOut(
        group_index=group_index,
        sentence_count=sentence_count,
        stars=stage.stars,
        best_accuracy=stage.best_accuracy,
        attempts=stage.attempts,
    )


@router.get("/continue/{material_id}", response_model=ContinueResponse)
def continue_practice(
    material_id: str, db: Annotated[Session, Depends(get_db)]
) -> ContinueResponse:
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
) -> GroupOut:
    user = _ensure_user(db)
    group = _load_group(db, user.id, material_id, group_index)
    if not group:
        raise HTTPException(404, "Group not found")
    return group


# ── Submit answer ──────────────────────────────────────────────────────


@router.post("/submit", response_model=SubmitResult)
def submit_answer(
    req: SubmitRequest, db: Annotated[Session, Depends(get_db)]
) -> SubmitResult:
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
def add_favorite(
    sentence_id: str, db: Annotated[Session, Depends(get_db)]
) -> dict[str, str]:
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
def remove_favorite(
    sentence_id: str, db: Annotated[Session, Depends(get_db)]
) -> dict[str, str]:
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
def get_wrongbook(db: Annotated[Session, Depends(get_db)]) -> list[SentenceOut]:
    user = _ensure_user(db)
    records = db.scalars(
        select(WrongRecord)
        .where(WrongRecord.user_id == user.id, WrongRecord.mastered == False)  # noqa: E712
        .order_by(WrongRecord.updated_at.desc())
    ).all()

    fav_ids = set(
        db.scalars(
            select(Favorite.sentence_id).where(Favorite.user_id == user.id)
        ).all()
    )

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
                is_favorite=s.id in fav_ids,
                wrong_count=r.wrong_count,
            )
        )
    return result


# ── Favorites list ─────────────────────────────────────────────────────


@router.get("/favorites", response_model=list[SentenceOut])
def get_favorites(db: Annotated[Session, Depends(get_db)]) -> list[SentenceOut]:
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
    wrong_map: dict[str, int] = {
        sentence_id: wrong_count
        for sentence_id, wrong_count in db.execute(
            select(WrongRecord.sentence_id, WrongRecord.wrong_count).where(
                WrongRecord.user_id == user_id,
                WrongRecord.mastered == False,  # noqa: E712
            )
        ).all()
    }

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
