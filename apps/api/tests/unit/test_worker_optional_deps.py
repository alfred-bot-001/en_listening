"""The heavy media deps are imported lazily; when absent the wrappers must
raise a clear, typed error rather than a bare ImportError."""

from pathlib import Path

import pytest

from listenflow.workers import download, transcribe


def test_download_without_yt_dlp_raises(monkeypatch) -> None:
    monkeypatch.setitem(__import__("sys").modules, "yt_dlp", None)
    with pytest.raises(download.DownloadError, match="yt-dlp is not installed"):
        download.download_media("https://x", Path("/tmp"), stem="s")


def test_transcribe_without_faster_whisper_raises(monkeypatch) -> None:
    monkeypatch.setitem(__import__("sys").modules, "faster_whisper", None)
    transcribe._load_model.cache_clear()
    with pytest.raises(transcribe.TranscriptionError, match="faster-whisper"):
        transcribe.transcribe_audio(Path("/tmp/a.wav"), model="unique-test-model")
    transcribe._load_model.cache_clear()
