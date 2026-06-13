"""yt-dlp wrapper for importing YouTube / Bilibili sources.

Downloads the best available audio plus any platform subtitles (manual first,
falling back to auto-generated). ``yt_dlp`` is imported lazily so the rest of
the app — and the test suite — never depends on it being installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

SUBTITLE_EXTS = {".srt", ".vtt"}
MEDIA_EXTS = {".m4a", ".mp3", ".webm", ".opus", ".mp4", ".mkv", ".wav", ".aac"}


class DownloadError(RuntimeError):
    """Raised when a remote source cannot be downloaded."""


@dataclass(frozen=True)
class DownloadResult:
    media_path: Path
    subtitle_path: Path | None


def download_media(
    url: str,
    dest_dir: Path,
    *,
    stem: str,
    subtitle_langs: tuple[str, ...] = ("en", "en-US", "en-GB"),
) -> DownloadResult:
    """Download audio + subtitles for ``url`` into ``dest_dir/{stem}.*``."""
    try:
        import yt_dlp
    except ImportError as exc:  # pragma: no cover - depends on optional dep
        raise DownloadError(
            "yt-dlp is not installed. Add it to run YouTube/Bilibili imports."
        ) from exc

    dest_dir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(dest_dir / f"{stem}.%(ext)s")
    options = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "writesubtitles": True,
        "writeautomaticsub": True,
        "subtitleslangs": list(subtitle_langs),
        "subtitlesformat": "srt/vtt/best",
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "ignoreerrors": False,
    }

    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            ydl.extract_info(url, download=True)
    except Exception as exc:  # pragma: no cover - network/path errors
        raise DownloadError(f"Download failed: {exc}") from exc

    return _classify_downloads(dest_dir, stem)


def _classify_downloads(dest_dir: Path, stem: str) -> DownloadResult:
    media_path: Path | None = None
    subtitle_path: Path | None = None

    for candidate in sorted(dest_dir.glob(f"{stem}*")):
        suffix = candidate.suffix.lower()
        if suffix in SUBTITLE_EXTS and subtitle_path is None:
            subtitle_path = candidate
        elif suffix in MEDIA_EXTS and media_path is None:
            media_path = candidate

    if media_path is None:
        raise DownloadError(
            "Download completed but no audio file was produced."
        )
    return DownloadResult(media_path=media_path, subtitle_path=subtitle_path)
