import shutil
import subprocess
from pathlib import Path

import pytest

from listenflow.workers import audio

FFMPEG = shutil.which("ffmpeg")
pytestmark = pytest.mark.skipif(FFMPEG is None, reason="ffmpeg required")


def _make_tone(path: Path, seconds: int = 5) -> Path:
    subprocess.run(
        [
            FFMPEG, "-y", "-f", "lavfi",
            "-i", f"sine=frequency=440:duration={seconds}",
            "-ar", "44100", "-ac", "2", str(path),
        ],
        check=True,
        capture_output=True,
    )
    return path


def test_probe_duration(tmp_path: Path) -> None:
    source = _make_tone(tmp_path / "tone.wav", seconds=5)
    duration = audio.probe_duration(source)
    assert duration is not None
    assert 4.5 < duration < 5.5


def test_extract_audio_is_mono_16k(tmp_path: Path) -> None:
    source = _make_tone(tmp_path / "tone.wav", seconds=3)
    dest = audio.extract_audio(source, tmp_path / "out" / "audio.wav")
    assert dest.exists()
    assert dest.stat().st_size > 0


def test_cut_clip_extracts_a_shorter_segment(tmp_path: Path) -> None:
    source = _make_tone(tmp_path / "tone.wav", seconds=6)
    clip = audio.cut_clip(source, tmp_path / "clips" / "c.mp3", start=1.0, end=3.0)
    assert clip.exists()
    clip_duration = audio.probe_duration(clip)
    assert clip_duration is not None
    assert 1.5 < clip_duration < 2.5


def test_missing_binary_raises(monkeypatch) -> None:
    monkeypatch.setattr(audio.shutil, "which", lambda _name: None)
    with pytest.raises(audio.FFmpegError, match="not found"):
        audio.probe_duration(Path("nope.wav"))
