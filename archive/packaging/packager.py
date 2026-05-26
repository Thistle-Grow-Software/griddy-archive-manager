"""Produce CMAF/fMP4 segments and an HLS manifest for one source file.

The work is split so the ffmpeg command is testable without a video file or
ffmpeg installed: :func:`build_ffmpeg_command` is a pure function returning the
argument list, and :func:`package_to_hls` runs it through an injectable runner
(``subprocess.run`` by default). The packager produces fragmented-MP4 (CMAF)
output — an ``init.mp4`` initialization segment, ``seg_NNNNN.m4s`` media
segments, and the ``master.m3u8`` playlist — at a ~6s target. H.264 video and
AAC audio are stream-copied; anything else is transcoded to them first, per the
per-stream plan from :mod:`archive.packaging.probe`.
"""

from __future__ import annotations

import logging
import subprocess
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path

from .keys import MANIFEST_NAME
from .probe import MediaProbe

logger = logging.getLogger("archive")

DEFAULT_SEGMENT_DURATION = 6
INIT_SEGMENT_NAME = "init.mp4"
SEGMENT_TEMPLATE = "seg_%05d.m4s"

# Transcode settings for the ~10 non-conforming outliers. CRF 20 / veryfast is a
# pragmatic visually-lossless-enough target for a one-time batch over a handful
# of files; audio normalizes to 160k AAC.
_TRANSCODE_VIDEO = ("-c:v", "libx264", "-preset", "veryfast", "-crf", "20")
_TRANSCODE_AUDIO = ("-c:a", "aac", "-b:a", "160k")

Runner = Callable[[Sequence[str]], None]


class PackagingError(RuntimeError):
    """Raised when ffmpeg fails to package a file."""


@dataclass(frozen=True)
class PackageResult:
    """Outcome of packaging one file into a local output directory."""

    manifest_path: Path
    segment_paths: list[Path]
    output_bytes: int
    transcoded: bool


def build_ffmpeg_command(
    source: Path,
    out_dir: Path,
    probe: MediaProbe,
    *,
    segment_duration: int = DEFAULT_SEGMENT_DURATION,
) -> list[str]:
    """Build the ffmpeg argument list for packaging ``source`` into ``out_dir``.

    Video and audio codecs are chosen independently from ``probe``: each stream
    is copied when already HLS-native, otherwise transcoded. When transcoding
    video, keyframes are forced every ``segment_duration`` seconds so the
    segmenter can cut clean ~6s boundaries; copied video is cut on its existing
    keyframes (the catalog's GOP is <=6s, so segments land near target).
    """
    cmd = ["ffmpeg", "-nostdin", "-y", "-i", str(source)]

    if probe.video.copy:
        cmd += ["-c:v", "copy"]
    else:
        cmd += list(_TRANSCODE_VIDEO)
        # Force keyframes on the segment grid so copy-cut boundaries are clean.
        cmd += ["-force_key_frames", f"expr:gte(t,n_forced*{segment_duration})"]

    if probe.audio.copy:
        cmd += ["-c:a", "copy"]
    else:
        cmd += list(_TRANSCODE_AUDIO)

    cmd += [
        "-f",
        "hls",
        "-hls_time",
        str(segment_duration),
        "-hls_playlist_type",
        "vod",
        "-hls_segment_type",
        "fmp4",
        "-hls_fmp4_init_filename",
        INIT_SEGMENT_NAME,
        "-hls_segment_filename",
        str(out_dir / SEGMENT_TEMPLATE),
        str(out_dir / MANIFEST_NAME),
    ]
    return cmd


def _default_runner(cmd: Sequence[str]) -> None:
    try:
        subprocess.run(cmd, capture_output=True, text=True, check=True)
    except FileNotFoundError as exc:
        raise PackagingError("ffmpeg executable not found on PATH") from exc
    except subprocess.CalledProcessError as exc:
        raise PackagingError(f"ffmpeg failed: {exc.stderr}") from exc


def package_to_hls(
    source: Path,
    out_dir: Path,
    probe: MediaProbe,
    *,
    segment_duration: int = DEFAULT_SEGMENT_DURATION,
    runner: Runner = _default_runner,
) -> PackageResult:
    """Package ``source`` into ``out_dir`` as CMAF/HLS and report what landed.

    ``out_dir`` is created if needed. After ffmpeg runs, the manifest must
    exist or :class:`PackagingError` is raised (ffmpeg can exit 0 yet write
    nothing if the input is degenerate). Returns the produced files and their
    total size on disk.
    """
    out_dir.mkdir(parents=True, exist_ok=True)
    cmd = build_ffmpeg_command(
        source, out_dir, probe, segment_duration=segment_duration
    )
    logger.debug("packaging %s -> %s", source, out_dir)
    runner(cmd)

    manifest_path = out_dir / MANIFEST_NAME
    if not manifest_path.is_file():
        raise PackagingError(f"ffmpeg produced no manifest for {source}")

    segment_paths = sorted(
        p for p in out_dir.iterdir() if p.is_file() and p.name != MANIFEST_NAME
    )
    output_bytes = manifest_path.stat().st_size + sum(
        p.stat().st_size for p in segment_paths
    )
    return PackageResult(
        manifest_path=manifest_path,
        segment_paths=segment_paths,
        output_bytes=output_bytes,
        transcoded=probe.needs_transcode,
    )
