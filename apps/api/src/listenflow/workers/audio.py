"""Thin wrappers around ffmpeg / ffprobe for audio extraction and clipping.

These shell out to the system ``ffmpeg``/``ffprobe`` binaries (declared as a
runtime dependency in the README / docker image). Each helper raises
:class:`FFmpegError` with captured stderr so the pipeline can surface a useful
message on the media job.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

# Sample rate / channel layout expected by faster-whisper.
WHISPER_SAMPLE_RATE = 16_000


class FFmpegError(RuntimeError):
    """Raised when an ffmpeg/ffprobe invocation fails."""


def _require(binary: str) -> str:
    path = shutil.which(binary)
    if path is None:
        raise FFmpegError(
            f"`{binary}` not found on PATH. Install ffmpeg to process audio/video."
        )
    return path


def _run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            cmd,
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:  # pragma: no cover - error path
        tail = (exc.stderr or "").strip().splitlines()[-5:]
        raise FFmpegError(
            f"{Path(cmd[0]).name} failed ({exc.returncode}): {' '.join(tail)}"
        ) from exc


def probe_duration(media_path: Path) -> float | None:
    """Return media duration in seconds, or ``None`` if it cannot be read."""
    ffprobe = _require("ffprobe")
    result = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(media_path),
        ]
    )
    try:
        data = json.loads(result.stdout)
        return float(data["format"]["duration"])
    except (json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None


def extract_audio(
    source: Path,
    dest: Path,
    *,
    sample_rate: int = WHISPER_SAMPLE_RATE,
) -> Path:
    """Extract a mono PCM WAV from any audio/video source for transcription."""
    ffmpeg = _require("ffmpeg")
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run(
        [
            ffmpeg,
            "-y",
            "-i",
            str(source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(sample_rate),
            "-c:a",
            "pcm_s16le",
            str(dest),
        ]
    )
    return dest


def cut_clip(source: Path, dest: Path, start: float, end: float) -> Path:
    """Cut ``[start, end)`` seconds of ``source`` into an mp3 clip at ``dest``."""
    ffmpeg = _require("ffmpeg")
    dest.parent.mkdir(parents=True, exist_ok=True)
    duration = max(end - start, 0.05)
    _run(
        [
            ffmpeg,
            "-y",
            "-ss",
            f"{start:.3f}",
            "-t",
            f"{duration:.3f}",
            "-i",
            str(source),
            "-vn",
            "-c:a",
            "libmp3lame",
            "-q:a",
            "4",
            str(dest),
        ]
    )
    return dest
