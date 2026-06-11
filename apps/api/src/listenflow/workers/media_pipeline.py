from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from listenflow.models import JobStatus, MediaJob, Sentence
from listenflow.modules.practice.domain import extract_keywords


@dataclass(frozen=True)
class PipelineStep:
    name: str
    progress: int


@dataclass(frozen=True)
class TranscriptSegment:
    text: str
    start_time: float
    end_time: float


PIPELINE_STEPS: tuple[PipelineStep, ...] = (
    PipelineStep("download_or_load_source", 10),
    PipelineStep("extract_audio", 25),
    PipelineStep("extract_or_transcribe_subtitles", 50),
    PipelineStep("segment_sentences", 70),
    PipelineStep("cut_audio_clips", 90),
    PipelineStep("extract_keywords", 100),
)


def plan_media_pipeline(material_id: UUID) -> list[tuple[UUID, PipelineStep]]:
    return [(material_id, step) for step in PIPELINE_STEPS]


def parse_transcript(content: str) -> list[TranscriptSegment]:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    if "-->" in normalized:
        return _parse_timed_transcript(normalized)
    return _parse_plain_text_transcript(normalized)


def process_media_job(
    db: Session,
    job_id: str,
    *,
    storage_root: Path,
    group_size: int = 10,
) -> MediaJob:
    job = db.scalar(select(MediaJob).where(MediaJob.id == job_id))
    if job is None:
        raise ValueError(f"Media job not found: {job_id}")

    material = job.material
    try:
        job.status = JobStatus.SPLITTING
        job.progress = 70
        db.flush()

        source_path = _resolve_transcript_path(
            storage_root=storage_root,
            file_path=material.file_path,
            subtitle_path=material.subtitle_path,
        )
        if source_path is None:
            raise ValueError(
                "No transcript file found yet. "
                "Upload .srt, .vtt, or .txt for MVP processing."
            )

        segments = parse_transcript(source_path.read_text(encoding="utf-8"))
        if not segments:
            raise ValueError("Transcript did not contain any usable sentences.")

        db.execute(delete(Sentence).where(Sentence.material_id == material.id))
        for index, segment in enumerate(segments):
            keywords = extract_keywords(segment.text)
            db.add(
                Sentence(
                    material_id=material.id,
                    group_index=index // group_size,
                    sentence_index=index % group_size,
                    text=segment.text,
                    start_time=segment.start_time,
                    end_time=segment.end_time,
                    keywords=json.dumps(keywords),
                )
            )

        material.subtitle_path = str(source_path.relative_to(storage_root))
        material.duration_seconds = max(segment.end_time for segment in segments)
        job.status = JobStatus.DONE
        job.progress = 100
        job.error_message = None
        db.commit()
    except Exception as exc:
        job.status = JobStatus.FAILED
        job.progress = 100
        job.error_message = str(exc)
        db.commit()

    db.refresh(job)
    return job


def _resolve_transcript_path(
    *,
    storage_root: Path,
    file_path: str | None,
    subtitle_path: str | None,
) -> Path | None:
    for rel_path in (subtitle_path, file_path):
        if rel_path is None:
            continue
        path = storage_root / rel_path
        if path.suffix.lower() in {".srt", ".vtt", ".txt"} and path.exists():
            return path
    return None


def _parse_timed_transcript(content: str) -> list[TranscriptSegment]:
    segments: list[TranscriptSegment] = []
    for block in re.split(r"\n{2,}", content):
        lines = [line.strip() for line in block.splitlines() if line.strip()]
        if not lines or lines[0].upper() == "WEBVTT":
            continue

        timing_index = next((i for i, line in enumerate(lines) if "-->" in line), None)
        if timing_index is None:
            continue

        start_raw, end_raw = lines[timing_index].split("-->", maxsplit=1)
        text_lines = lines[timing_index + 1 :]
        text = _clean_caption_text(" ".join(text_lines))
        if text:
            segments.append(
                TranscriptSegment(
                    text=text,
                    start_time=_parse_timestamp(start_raw),
                    end_time=_parse_timestamp(end_raw),
                )
            )
    return segments


def _parse_plain_text_transcript(content: str) -> list[TranscriptSegment]:
    sentences = [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?])\s+", content)
        if sentence.strip()
    ]
    return [
        TranscriptSegment(
            text=sentence,
            start_time=index * 3.0,
            end_time=(index + 1) * 3.0,
        )
        for index, sentence in enumerate(sentences)
    ]


def _parse_timestamp(value: str) -> float:
    clean = value.strip().split()[0].replace(",", ".")
    parts = clean.split(":")
    seconds = float(parts[-1])
    minutes = int(parts[-2]) if len(parts) >= 2 else 0
    hours = int(parts[-3]) if len(parts) >= 3 else 0
    return hours * 3600 + minutes * 60 + seconds


def _clean_caption_text(value: str) -> str:
    without_tags = re.sub(r"<[^>]+>", "", value)
    without_speaker = re.sub(r"^\s*[-\w ]+:\s*", "", without_tags)
    return re.sub(r"\s+", " ", without_speaker).strip()
