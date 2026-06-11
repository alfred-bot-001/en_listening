from __future__ import annotations

import enum
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from listenflow.db import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.utcnow()


# ── Enums ──────────────────────────────────────────────────────────────


class MaterialType(enum.StrEnum):
    VIDEO = "video"
    AUDIO = "audio"
    YOUTUBE = "youtube"
    BILIBILI = "bilibili"


class JobStatus(enum.StrEnum):
    PENDING = "pending"
    DOWNLOADING = "downloading"
    EXTRACTING_AUDIO = "extracting_audio"
    TRANSCRIBING = "transcribing"
    SPLITTING = "splitting"
    DONE = "done"
    FAILED = "failed"


# ── Material ───────────────────────────────────────────────────────────


class Material(Base):
    __tablename__ = "materials"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_type: Mapped[MaterialType] = mapped_column(
        Enum(MaterialType), nullable=False
    )
    source_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    subtitle_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(200), nullable=True)
    duration_seconds: Mapped[float | None] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    # relationships
    jobs: Mapped[list[MediaJob]] = relationship(
        back_populates="material", cascade="all, delete-orphan"
    )
    sentences: Mapped[list[Sentence]] = relationship(
        back_populates="material", cascade="all, delete-orphan"
    )


# ── MediaJob ───────────────────────────────────────────────────────────


class MediaJob(Base):
    __tablename__ = "media_jobs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    material_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("materials.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[JobStatus] = mapped_column(
        Enum(JobStatus), default=JobStatus.PENDING
    )
    progress: Mapped[float] = mapped_column(Float, default=0.0)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    material: Mapped[Material] = relationship(back_populates="jobs")


# ── Sentence ───────────────────────────────────────────────────────────


class Sentence(Base):
    __tablename__ = "sentences"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    material_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("materials.id", ondelete="CASCADE"), nullable=False
    )
    group_index: Mapped[int] = mapped_column(Integer, nullable=False)
    sentence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_time: Mapped[float] = mapped_column(Float, nullable=False)
    end_time: Mapped[float] = mapped_column(Float, nullable=False)
    audio_path: Mapped[str | None] = mapped_column(Text, nullable=True)
    keywords: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    material: Mapped[Material] = relationship(back_populates="sentences")
    favorites: Mapped[list[Favorite]] = relationship(
        back_populates="sentence", cascade="all, delete-orphan"
    )
    wrong_records: Mapped[list[WrongRecord]] = relationship(
        back_populates="sentence", cascade="all, delete-orphan"
    )
    attempts: Mapped[list[PracticeAttempt]] = relationship(
        back_populates="sentence", cascade="all, delete-orphan"
    )


# ── User (simplified for MVP - single user) ───────────────────────────


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    username: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    progress: Mapped[list[Progress]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    favorites: Mapped[list[Favorite]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    wrong_records: Mapped[list[WrongRecord]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


# ── Progress ───────────────────────────────────────────────────────────


class Progress(Base):
    __tablename__ = "progress"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    material_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("materials.id", ondelete="CASCADE"), nullable=False
    )
    group_index: Mapped[int] = mapped_column(Integer, nullable=False)
    sentence_index: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="progress")


# ── Favorite ───────────────────────────────────────────────────────────


class Favorite(Base):
    __tablename__ = "favorites"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    sentence_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("sentences.id", ondelete="CASCADE"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[User] = relationship(back_populates="favorites")
    sentence: Mapped[Sentence] = relationship(back_populates="favorites")


# ── WrongRecord (错题集) ──────────────────────────────────────────────


class WrongRecord(Base):
    __tablename__ = "wrong_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    sentence_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("sentences.id", ondelete="CASCADE"), nullable=False
    )
    wrong_count: Mapped[int] = mapped_column(Integer, default=1)
    mastered: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="wrong_records")
    sentence: Mapped[Sentence] = relationship(back_populates="wrong_records")


# ── PracticeAttempt ────────────────────────────────────────────────────


class PracticeAttempt(Base):
    __tablename__ = "practice_attempts"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=_uuid)
    user_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    sentence_id: Mapped[str] = mapped_column(
        String(32), ForeignKey("sentences.id", ondelete="CASCADE"), nullable=False
    )
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    user_input: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    sentence: Mapped[Sentence] = relationship(back_populates="attempts")
