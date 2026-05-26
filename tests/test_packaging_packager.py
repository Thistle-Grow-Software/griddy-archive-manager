"""Tests for ffmpeg command construction and the packaging wrapper."""

from __future__ import annotations

from pathlib import Path

import pytest

from archive.packaging.packager import (
    INIT_SEGMENT_NAME,
    PackagingError,
    build_ffmpeg_command,
    package_to_hls,
)
from archive.packaging.probe import MediaProbe


def make_probe(video="h264", audio="aac"):
    return MediaProbe(Path("/in.mp4"), video, audio, 10.0)


def test_copy_command_streams_copies_both(tmp_path):
    cmd = build_ffmpeg_command(
        Path("/in.mp4"), tmp_path, make_probe("h264", "aac"), segment_duration=6
    )
    assert "-c:v" in cmd and cmd[cmd.index("-c:v") + 1] == "copy"
    assert "-c:a" in cmd and cmd[cmd.index("-c:a") + 1] == "copy"
    assert "libx264" not in cmd
    # CMAF/fMP4 output at the requested target.
    assert "fmp4" in cmd
    assert cmd[cmd.index("-hls_time") + 1] == "6"
    assert cmd[-1].endswith("master.m3u8")


def test_transcode_command_reencodes_video_and_forces_keyframes(tmp_path):
    cmd = build_ffmpeg_command(
        Path("/in.mp4"), tmp_path, make_probe("vp9", "aac"), segment_duration=4
    )
    assert "libx264" in cmd
    assert cmd[cmd.index("-c:a") + 1] == "copy"  # AAC audio still copied
    assert "-force_key_frames" in cmd
    assert "expr:gte(t,n_forced*4)" in cmd


def test_transcode_command_reencodes_audio_only(tmp_path):
    cmd = build_ffmpeg_command(Path("/in.mp4"), tmp_path, make_probe("h264", "ac3"))
    assert cmd[cmd.index("-c:v") + 1] == "copy"
    assert "aac" in cmd  # audio transcoded to AAC
    assert "libx264" not in cmd


def _fake_runner_writing_output(tmp_path):
    """A runner that emulates ffmpeg writing a manifest + segments."""

    def runner(cmd):
        out_dir = Path(cmd[-1]).parent
        (out_dir / "master.m3u8").write_text("#EXTM3U\n")
        (out_dir / INIT_SEGMENT_NAME).write_bytes(b"init")
        (out_dir / "seg_00000.m4s").write_bytes(b"segment-bytes")

    return runner


def test_package_to_hls_collects_outputs(tmp_path):
    out = tmp_path / "out"
    result = package_to_hls(
        Path("/in.mp4"),
        out,
        make_probe("h264", "aac"),
        runner=_fake_runner_writing_output(tmp_path),
    )
    assert result.manifest_path == out / "master.m3u8"
    assert result.transcoded is False
    seg_names = {p.name for p in result.segment_paths}
    assert seg_names == {INIT_SEGMENT_NAME, "seg_00000.m4s"}
    # output_bytes covers the manifest and every segment.
    assert result.output_bytes == len("#EXTM3U\n") + len(b"init") + len(
        b"segment-bytes"
    )


def test_package_to_hls_marks_transcoded(tmp_path):
    result = package_to_hls(
        Path("/in.mp4"),
        tmp_path / "out",
        make_probe("av1", "opus"),
        runner=_fake_runner_writing_output(tmp_path),
    )
    assert result.transcoded is True


def test_package_to_hls_raises_when_no_manifest(tmp_path):
    def empty_runner(cmd):
        return None  # ffmpeg "succeeded" but wrote nothing

    with pytest.raises(PackagingError):
        package_to_hls(
            Path("/in.mp4"),
            tmp_path / "out",
            make_probe(),
            runner=empty_runner,
        )
