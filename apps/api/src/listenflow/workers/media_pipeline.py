"""End-to-end media pipeline.

Turns a raw material (uploaded file or remote URL) into practice-ready
sentences with per-sentence audio clips:

    download (remote) -> extract audio -> subtitles or whisper transcription
    -> sentence segmentation + grouping -> audio clips -> keyword extraction

Each stage updates the :class:`MediaJob` status/progress (committed as it goes
so the UI can poll), and any failure is captured on the job's ``error_message``.

The heavy external tools (``ffmpeg``, ``yt-dlp``, ``faster-whisper``) live in
sibling modules and are imported lazily, so this module stays importable — and
unit-testable with fakes — without those dependencies installed.
"""

from __future__ import annotations

import json
import re
import uuid
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from listenflow.models import JobStatus, Material, MaterialType, MediaJob, Sentence
from listenflow.workers import audio, download, transcribe
from listenflow.workers.keyword_analyzer import analyze_keywords

# Extensions we treat as ready-to-parse transcripts rather than playable media.
TRANSCRIPT_EXTS = {".srt", ".vtt", ".txt"}


@dataclass(frozen=True)
class PipelineStep:
    name: str
    progress: int


@dataclass(frozen=True)
class TranscriptSegment:
    text: str
    start_time: float
    end_time: float


@dataclass(frozen=True)
class SourceFiles:
    media_path: Path | None
    subtitle_path: Path | None


PIPELINE_STEPS: tuple[PipelineStep, ...] = (
    PipelineStep("download_or_load_source", 10),
    PipelineStep("extract_audio", 30),
    PipelineStep("extract_or_transcribe_subtitles", 50),
    PipelineStep("segment_sentences", 70),
    PipelineStep("cut_audio_clips", 90),
    PipelineStep("extract_keywords", 100),
)


def plan_media_pipeline(material_id: UUID) -> list[tuple[UUID, PipelineStep]]:
    return [(material_id, step) for step in PIPELINE_STEPS]


# ── Orchestration ──────────────────────────────────────────────────────


def process_media_job(
    db: Session,
    job_id: str,
    *,
    storage_root: Path,
    group_size: int | None = None,
) -> MediaJob:
    job = db.scalar(select(MediaJob).where(MediaJob.id == job_id))
    if job is None:
        raise ValueError(f"Media job not found: {job_id}")

    if group_size is None:
        from listenflow.core.config import get_settings

        group_size = get_settings().group_size

    material = job.material
    try:
        source = _acquire_source(db, job, material, storage_root)
        segments = _build_segments(db, job, material, source, storage_root)
        if not segments:
            raise ValueError("Transcript did not contain any usable sentences.")

        _set_status(db, job, JobStatus.SPLITTING, 70)
        _persist_sentences(
            db,
            material=material,
            segments=segments,
            clip_source=source.media_path,
            storage_root=storage_root,
            group_size=group_size,
        )
        material.duration_seconds = _resolve_duration(source.media_path, segments)

        _set_status(db, job, JobStatus.DONE, 100, error_message=None)
    except Exception as exc:
        db.rollback()
        job = db.scalar(select(MediaJob).where(MediaJob.id == job_id))
        if job is not None:
            job.status = JobStatus.FAILED
            job.progress = 100.0
            job.error_message = str(exc)[:1000]
            db.commit()
            db.refresh(job)
        return job  # type: ignore[return-value]

    db.refresh(job)
    return job


def _acquire_source(
    db: Session, job: MediaJob, material: Material, storage_root: Path
) -> SourceFiles:
    """Resolve (and download, if remote) the media + subtitle files."""
    if material.source_type in (MaterialType.YOUTUBE, MaterialType.BILIBILI):
        if not material.source_url:
            raise ValueError("Remote material is missing a source URL.")
        _set_status(db, job, JobStatus.DOWNLOADING, 10)
        result = download.download_media(
            material.source_url,
            storage_root / "uploads",
            stem=material.id,
        )
        material.file_path = str(result.media_path.relative_to(storage_root))
        if result.subtitle_path is not None:
            material.subtitle_path = str(
                result.subtitle_path.relative_to(storage_root)
            )
        db.commit()
        return SourceFiles(
            media_path=result.media_path, subtitle_path=result.subtitle_path
        )

    # Uploaded file(s): classify into media vs. transcript.
    media_path: Path | None = None
    subtitle_path: Path | None = None
    for rel_path in (material.subtitle_path, material.file_path):
        if not rel_path:
            continue
        path = storage_root / rel_path
        if not path.exists():
            continue
        if path.suffix.lower() in TRANSCRIPT_EXTS:
            subtitle_path = subtitle_path or path
        else:
            media_path = media_path or path

    if media_path is None and subtitle_path is None:
        raise ValueError(
            "No source file found. Upload media or a .srt/.vtt/.txt transcript."
        )
    return SourceFiles(media_path=media_path, subtitle_path=subtitle_path)


def _build_segments(
    db: Session,
    job: MediaJob,
    material: Material,
    source: SourceFiles,
    storage_root: Path,
) -> list[TranscriptSegment]:
    """Prefer existing subtitles; otherwise extract audio and transcribe."""
    if source.subtitle_path is not None:
        _set_status(db, job, JobStatus.SPLITTING, 50)
        content = source.subtitle_path.read_text(encoding="utf-8", errors="ignore")
        segments = parse_transcript(content)
        if segments:
            material.subtitle_path = str(
                source.subtitle_path.relative_to(storage_root)
            )
            return segments
        # Empty subtitle file: fall through to transcription when possible.

    if source.media_path is None:
        raise ValueError("No subtitles found and no audio/video to transcribe.")

    from listenflow.core.config import get_settings

    settings = get_settings()

    _set_status(db, job, JobStatus.EXTRACTING_AUDIO, 30)
    audio_wav = audio.extract_audio(
        source.media_path, storage_root / "audio" / f"{material.id}.wav"
    )
    material.audio_path = str(audio_wav.relative_to(storage_root))
    db.commit()

    _set_status(db, job, JobStatus.TRANSCRIBING, 50)
    whisper_segments = transcribe.transcribe_audio(
        audio_wav,
        model=settings.whisper_model,
        device=settings.whisper_device,
        compute_type=settings.whisper_compute_type,
    )
    return [
        TranscriptSegment(
            text=seg.text, start_time=seg.start_time, end_time=seg.end_time
        )
        for seg in whisper_segments
    ]


def _persist_sentences(
    db: Session,
    *,
    material: Material,
    segments: list[TranscriptSegment],
    clip_source: Path | None,
    storage_root: Path,
    group_size: int,
) -> None:
    db.execute(delete(Sentence).where(Sentence.material_id == material.id))
    clips_dir = storage_root / "clips" / material.id

    all_keywords = analyze_keywords([seg.text for seg in segments])

    for index, segment in enumerate(segments):
        sentence_id = uuid.uuid4().hex
        keywords = all_keywords[index]
        audio_rel: str | None = None
        if clip_source is not None:
            clip_path = clips_dir / f"{sentence_id}.mp3"
            try:
                audio.cut_clip(
                    clip_source, clip_path, segment.start_time, segment.end_time
                )
                audio_rel = str(clip_path.relative_to(storage_root))
            except audio.FFmpegError:
                audio_rel = None
        db.add(
            Sentence(
                id=sentence_id,
                material_id=material.id,
                group_index=index // group_size,
                sentence_index=index % group_size,
                text=segment.text,
                start_time=segment.start_time,
                end_time=segment.end_time,
                audio_path=audio_rel,
                keywords=json.dumps(keywords),
            )
        )
    db.commit()


def _resolve_duration(
    media_path: Path | None, segments: list[TranscriptSegment]
) -> float:
    if media_path is not None:
        probed = audio.probe_duration(media_path)
        if probed is not None:
            return probed
    return max((segment.end_time for segment in segments), default=0.0)


_KEEP = object()


def _set_status(
    db: Session,
    job: MediaJob,
    status: JobStatus,
    progress: float,
    *,
    error_message: object = _KEEP,
) -> None:
    job.status = status
    job.progress = float(progress)
    if error_message is not _KEEP:
        job.error_message = error_message  # type: ignore[assignment]
    db.commit()


# ── Transcript parsing (SRT / VTT / plain text) ────────────────────────


def parse_transcript(content: str) -> list[TranscriptSegment]:
    normalized = content.replace("\r\n", "\n").replace("\r", "\n").strip()
    if "-->" in normalized:
        return _parse_timed_transcript(normalized)
    return _parse_plain_text_transcript(normalized)


def _parse_timed_transcript(content: str) -> list[TranscriptSegment]:
    cues: list[TranscriptSegment] = []
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
            cues.append(
                TranscriptSegment(
                    text=text,
                    start_time=_parse_timestamp(start_raw),
                    end_time=_parse_timestamp(end_raw),
                )
            )

    return _resegment_by_sentence(cues)


def _resegment_by_sentence(
    cues: list[TranscriptSegment],
) -> list[TranscriptSegment]:
    """Stitch cues together and re-cut at sentence boundaries.

    YouTube auto-captions use a sliding ~5-second window with no respect for
    sentence boundaries, so a cue often holds the tail of one sentence and
    the head of the next ("husband Dan. We are going to give you"). Join the
    cue text into one stream, split on .!? followed by whitespace, and map
    each new sentence back to a [start, end] by interpolating timestamps
    inside the cue that contains each end of the sentence.
    """
    if not cues:
        return cues

    # Concatenate cue text with a space separator, recording where each cue
    # ends in the joined string so we can map char offsets back to time.
    pieces: list[str] = []
    boundaries: list[int] = []  # cumulative end offset for each cue
    cursor = 0
    for cue in cues:
        text = cue.text.strip()
        if pieces:
            pieces.append(" ")
            cursor += 1
        pieces.append(text)
        cursor += len(text)
        boundaries.append(cursor)
    full = "".join(pieces)

    sentences = [s for s in re.split(r"(?<=[.!?])\s+", full) if s.strip()]
    if not sentences:
        return cues

    out: list[TranscriptSegment] = []
    scan = 0
    for sent in sentences:
        idx = full.find(sent, scan)
        if idx < 0:
            continue  # shouldn't happen; skip if it does
        scan = idx + len(sent)

        # Cue range that this sentence's text falls into.
        start_cue = _cue_at_offset(boundaries, idx)
        end_cue = _cue_at_offset(boundaries, idx + len(sent) - 1)
        start_time = cues[start_cue].start_time
        end_time = cues[end_cue].end_time

        # YouTube auto-caption cues overlap in time (they're a sliding read
        # window, not "when this was said"). Force monotonicity against the
        # previous sentence and guarantee a non-trivial clip length so
        # ffmpeg's -ss/-t always produces a valid mp3.
        if out and start_time < out[-1].end_time:
            start_time = out[-1].end_time
        if end_time < start_time + 0.5:
            end_time = start_time + 0.5

        out.append(
            TranscriptSegment(
                text=sent.strip(),
                start_time=start_time,
                end_time=end_time,
            )
        )
    return out


def _cue_at_offset(boundaries: list[int], offset: int) -> int:
    for i, end in enumerate(boundaries):
        if offset < end:
            return i
    return len(boundaries) - 1


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
    # YouTube auto-captions mark speaker turns with `>>` (sometimes mid-cue,
    # since cues are a sliding window over the dialog). Drop them.
    without_marker = re.sub(r"\s*>>\s*", " ", without_speaker)
    return re.sub(r"\s+", " ", without_marker).strip()
