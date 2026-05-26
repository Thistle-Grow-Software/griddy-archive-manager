"""Probe source files with ``ffprobe`` to decide how each stream is packaged.

The TGF-337 catalog report (``video_stats.md``) found the archive is ~99%
H.264 video / AAC audio, which segments into HLS with a lossless
``ffmpeg -c copy`` remux. The ~10 outliers (VP9/AV1/HEVC video, Opus/AC-3
audio) have to be transcoded to H.264/AAC first. This module turns a file
into a :class:`MediaProbe` and from there a per-stream copy/transcode plan
so video and audio are each handled independently — an H.264 video with an
AC-3 audio track copies the video and only re-encodes the audio.
"""

from __future__ import annotations

import json
import logging
import subprocess
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("archive")

# Codecs that need no re-encode to live in a CMAF/HLS stream. Everything else
# is transcoded to these before segmenting.
HLS_NATIVE_VIDEO_CODEC = "h264"
HLS_NATIVE_AUDIO_CODEC = "aac"

# Hard ceiling on how long ffprobe may run on a single file. The catalog tops
# out around 22 GiB; metadata-only probes return in well under this.
PROBE_TIMEOUT_SECONDS = 60


class ProbeError(RuntimeError):
    """Raised when ffprobe cannot be run or returns unusable output."""


@dataclass(frozen=True)
class StreamPlan:
    """Whether a single stream can be stream-copied or must be transcoded."""

    codec: str
    copy: bool


@dataclass(frozen=True)
class MediaProbe:
    """The packaging-relevant facts about one source file."""

    path: Path
    video_codec: str
    audio_codec: str
    duration_seconds: float | None

    @property
    def video(self) -> StreamPlan:
        return StreamPlan(
            codec=self.video_codec,
            copy=self.video_codec == HLS_NATIVE_VIDEO_CODEC,
        )

    @property
    def audio(self) -> StreamPlan:
        # A file with no audio track ("") needs no audio handling and is
        # treated as copyable so it does not force a transcode on its own.
        return StreamPlan(
            codec=self.audio_codec,
            copy=self.audio_codec in ("", HLS_NATIVE_AUDIO_CODEC),
        )

    @property
    def needs_transcode(self) -> bool:
        """True when either stream must be re-encoded for HLS."""
        return not (self.video.copy and self.audio.copy)


def _run_ffprobe(path: Path) -> dict:
    try:
        result = subprocess.run(
            [
                "ffprobe",
                "-v",
                "error",
                "-print_format",
                "json",
                "-show_format",
                "-show_streams",
                str(path),
            ],
            capture_output=True,
            text=True,
            check=True,
            timeout=PROBE_TIMEOUT_SECONDS,
        )
    except FileNotFoundError as exc:  # ffprobe not on PATH
        raise ProbeError("ffprobe executable not found on PATH") from exc
    except subprocess.TimeoutExpired as exc:
        raise ProbeError(f"ffprobe timed out probing {path}") from exc
    except subprocess.CalledProcessError as exc:
        raise ProbeError(f"ffprobe failed for {path}: {exc.stderr}") from exc

    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError(f"ffprobe returned invalid JSON for {path}") from exc


def probe_media(path: Path) -> MediaProbe:
    """Probe ``path`` and return its first video/audio codecs and duration.

    Raises :class:`ProbeError` if ffprobe cannot run, times out, or reports no
    video stream (a file with no video is not packageable game film).
    """
    info = _run_ffprobe(path)
    streams = info.get("streams", [])

    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    if video is None:
        raise ProbeError(f"no video stream found in {path}")
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)

    duration = info.get("format", {}).get("duration")
    try:
        duration_seconds = float(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration_seconds = None

    return MediaProbe(
        path=path,
        video_codec=video.get("codec_name", ""),
        audio_codec=audio.get("codec_name", "") if audio else "",
        duration_seconds=duration_seconds,
    )
