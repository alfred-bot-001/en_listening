"""Materials routes - real database-backed CRUD + job submission."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from listenflow.db import get_db
from listenflow.models import JobStatus, Material, MaterialType, MediaJob, Sentence
from listenflow.workers.keyword_analyzer import analyze_keywords
from listenflow.workers.media_pipeline import process_media_job
from listenflow.workers.tasks import submit_media_job

router = APIRouter(prefix="/api/materials", tags=["materials"])


# ── Schemas ────────────────────────────────────────────────────────────


class MaterialOut(BaseModel):
    id: str
    title: str
    source_type: str
    source_url: str | None
    category: str | None
    duration_seconds: float | None
    job_status: str | None

    model_config = {"from_attributes": True}


class ImportURLRequest(BaseModel):
    url: str
    title: str | None = None


class JobOut(BaseModel):
    id: str
    material_id: str
    status: str
    progress: float
    error_message: str | None

    model_config = {"from_attributes": True}


# ── List ───────────────────────────────────────────────────────────────


@router.get("", response_model=list[MaterialOut])
def list_materials(
    db: Annotated[Session, Depends(get_db)],
    category: str | None = None,
    source_type: str | None = None,
) -> list[MaterialOut]:
    stmt = select(Material).options(joinedload(Material.jobs))
    if category:
        stmt = stmt.where(Material.category == category)
    if source_type:
        stmt = stmt.where(Material.source_type == source_type)
    stmt = stmt.order_by(Material.created_at.desc())
    materials = db.scalars(stmt).unique().all()
    result = []
    for m in materials:
        latest_job = m.jobs[-1] if m.jobs else None
        result.append(
            MaterialOut(
                id=m.id,
                title=m.title,
                source_type=m.source_type.value,
                source_url=m.source_url,
                category=m.category,
                duration_seconds=m.duration_seconds,
                job_status=latest_job.status.value if latest_job else None,
            )
        )
    return result


# ── Upload file ────────────────────────────────────────────────────────


@router.post("/upload", response_model=MaterialOut, status_code=201)
def upload_file(
    file: Annotated[UploadFile, File()],
    db: Annotated[Session, Depends(get_db)],
    title: Annotated[str | None, Form()] = None,
) -> MaterialOut:
    import os
    import uuid

    from listenflow.core.config import get_settings

    settings = get_settings()
    material_id = uuid.uuid4().hex
    ext = os.path.splitext(file.filename or "video.mp4")[1]
    rel_path = f"uploads/{material_id}{ext}"
    abs_path = settings.storage_root / rel_path
    abs_path.parent.mkdir(parents=True, exist_ok=True)

    with open(abs_path, "wb") as f:
        content = file.file.read()
        f.write(content)

    stype = (
        MaterialType.VIDEO
        if ext in (".mp4", ".mkv", ".avi", ".mov", ".webm")
        else MaterialType.AUDIO
    )

    material = Material(
        id=material_id,
        title=title or file.filename or "Untitled",
        source_type=stype,
        file_path=rel_path,
    )
    db.add(material)

    job = MediaJob(
        id=uuid.uuid4().hex, material_id=material_id, status=JobStatus.PENDING
    )
    db.add(job)
    db.commit()

    # Kick off the media pipeline (sync/thread/dramatiq per settings.job_runner).
    submit_media_job(db, job.id)

    db.refresh(material)
    db.refresh(job)

    return MaterialOut(
        id=material.id,
        title=material.title,
        source_type=material.source_type.value,
        source_url=material.source_url,
        category=material.category,
        duration_seconds=material.duration_seconds,
        job_status=job.status.value,
    )


# ── Import URL ─────────────────────────────────────────────────────────


@router.post("/import", response_model=MaterialOut, status_code=201)
def import_url(
    req: ImportURLRequest, db: Annotated[Session, Depends(get_db)]
) -> MaterialOut:
    import uuid

    url = req.url
    if "youtube.com" in url or "youtu.be" in url:
        stype = MaterialType.YOUTUBE
    elif "bilibili.com" in url or "b23.tv" in url:
        stype = MaterialType.BILIBILI
    else:
        raise HTTPException(
            400, "Unsupported URL. Only YouTube and Bilibili are supported."
        )

    material_id = uuid.uuid4().hex
    material = Material(
        id=material_id,
        title=req.title or "Imported from URL",
        source_type=stype,
        source_url=url,
    )
    db.add(material)

    job = MediaJob(
        id=uuid.uuid4().hex, material_id=material_id, status=JobStatus.PENDING
    )
    db.add(job)
    db.commit()

    # Download + transcribe in the background (or inline in eager mode).
    submit_media_job(db, job.id)

    db.refresh(material)
    db.refresh(job)

    return MaterialOut(
        id=material.id,
        title=material.title,
        source_type=material.source_type.value,
        source_url=material.source_url,
        category=material.category,
        duration_seconds=material.duration_seconds,
        job_status=job.status.value,
    )


# ── Get job status ─────────────────────────────────────────────────────


@router.get("/{material_id}/job", response_model=JobOut)
def get_job_status(
    material_id: str, db: Annotated[Session, Depends(get_db)]
) -> JobOut:
    job = db.scalar(
        select(MediaJob)
        .where(MediaJob.material_id == material_id)
        .order_by(MediaJob.created_at.desc())
        .limit(1)
    )
    if not job:
        raise HTTPException(404, "No job found for this material")
    return JobOut(
        id=job.id,
        material_id=job.material_id,
        status=job.status.value,
        progress=job.progress,
        error_message=job.error_message,
    )


@router.post("/{material_id}/process", response_model=JobOut)
def process_material(
    material_id: str, db: Annotated[Session, Depends(get_db)]
) -> JobOut:
    from listenflow.core.config import get_settings

    job = db.scalar(
        select(MediaJob)
        .where(MediaJob.material_id == material_id)
        .order_by(MediaJob.created_at.desc())
        .limit(1)
    )
    if not job:
        raise HTTPException(404, "No job found for this material")

    processed = process_media_job(
        db,
        job.id,
        storage_root=get_settings().storage_root,
    )
    return JobOut(
        id=processed.id,
        material_id=processed.material_id,
        status=processed.status.value,
        progress=processed.progress,
        error_message=processed.error_message,
    )


# ── Re-analyze keywords ────────────────────────────────────────────────


class ReanalyzeOut(BaseModel):
    material_id: str
    sentence_count: int


@router.post("/{material_id}/reanalyze", response_model=ReanalyzeOut)
def reanalyze_keywords(
    material_id: str, db: Annotated[Session, Depends(get_db)]
) -> ReanalyzeOut:
    """Re-run keyword analysis (LLM) over every sentence of this material."""
    import json as _json

    material = db.get(Material, material_id)
    if not material:
        raise HTTPException(404, "Material not found")

    sentences = list(
        db.scalars(
            select(Sentence)
            .where(Sentence.material_id == material_id)
            .order_by(Sentence.group_index, Sentence.sentence_index)
        ).all()
    )
    if not sentences:
        raise HTTPException(400, "Material has no sentences yet")

    new_keywords = analyze_keywords([s.text for s in sentences])
    for sentence, keywords in zip(sentences, new_keywords, strict=True):
        sentence.keywords = _json.dumps(keywords)
    db.commit()
    return ReanalyzeOut(material_id=material_id, sentence_count=len(sentences))


# ── Delete material ────────────────────────────────────────────────────


@router.delete("/{material_id}", status_code=204)
def delete_material(
    material_id: str, db: Annotated[Session, Depends(get_db)]
) -> None:
    material = db.get(Material, material_id)
    if not material:
        raise HTTPException(404, "Material not found")
    db.delete(material)
    db.commit()
