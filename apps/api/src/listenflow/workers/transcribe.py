"""faster-whisper transcription wrapper.

The model is loaded lazily and cached per (model, device, compute_type) so the
first transcription pays the load cost and later jobs reuse it. ``faster_whisper``
is imported lazily so the package is only required when actually transcribing.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


class TranscriptionError(RuntimeError):
    """Raised when transcription cannot be performed."""


@dataclass(frozen=True)
class Segment:
    text: str
    start_time: float
    end_time: float


@lru_cache(maxsize=2)
def _load_model(model: str, device: str, compute_type: str) -> Any:
    try:
        from faster_whisper import WhisperModel
    except ImportError as exc:  # pragma: no cover - depends on optional dep
        raise TranscriptionError(
            "faster-whisper is not installed. Add it to transcribe audio without "
            "existing subtitles."
        ) from exc
    return WhisperModel(model, device=device, compute_type=compute_type)


def transcribe_audio(
    audio_path: Path,
    *,
    model: str = "base.en",
    device: str = "cpu",
    compute_type: str = "int8",
    language: str | None = "en",
) -> list[Segment]:
    """Transcribe ``audio_path`` into timestamped segments."""
    whisper = _load_model(model, device, compute_type)
    try:
        raw_segments, _info = whisper.transcribe(
            str(audio_path),
            language=language,
            vad_filter=True,
        )
    except Exception as exc:  # pragma: no cover - runtime model errors
        raise TranscriptionError(f"Transcription failed: {exc}") from exc

    segments: list[Segment] = []
    for seg in raw_segments:
        text = (seg.text or "").strip()
        if not text:
            continue
        segments.append(
            Segment(text=text, start_time=float(seg.start), end_time=float(seg.end))
        )
    return segments
