"""Tests for ffprobe-driven codec inspection and the copy/transcode plan."""

from __future__ import annotations

from pathlib import Path

import pytest

from archive.packaging import probe as probe_mod
from archive.packaging.probe import MediaProbe, ProbeError, probe_media


def make_probe(video="h264", audio="aac"):
    return MediaProbe(
        path=Path("/x.mp4"),
        video_codec=video,
        audio_codec=audio,
        duration_seconds=10.0,
    )


def test_h264_aac_copies_both_streams():
    p = make_probe("h264", "aac")
    assert p.video.copy is True
    assert p.audio.copy is True
    assert p.needs_transcode is False


@pytest.mark.parametrize("video", ["vp9", "av1", "hevc"])
def test_non_native_video_forces_transcode(video):
    p = make_probe(video, "aac")
    assert p.video.copy is False
    assert p.audio.copy is True  # audio still copyable
    assert p.needs_transcode is True


@pytest.mark.parametrize("audio", ["opus", "ac3"])
def test_non_native_audio_forces_transcode_but_keeps_video_copy(audio):
    p = make_probe("h264", audio)
    assert p.video.copy is True
    assert p.audio.copy is False
    assert p.needs_transcode is True


def test_missing_audio_track_does_not_force_transcode():
    p = make_probe("h264", "")
    assert p.audio.copy is True
    assert p.needs_transcode is False


def test_probe_media_parses_streams(monkeypatch):
    payload = {
        "format": {"duration": "3600.5"},
        "streams": [
            {"codec_type": "video", "codec_name": "h264"},
            {"codec_type": "audio", "codec_name": "aac"},
        ],
    }
    monkeypatch.setattr(probe_mod, "_run_ffprobe", lambda path: payload)

    result = probe_media(Path("/games/x.mp4"))

    assert result.video_codec == "h264"
    assert result.audio_codec == "aac"
    assert result.duration_seconds == pytest.approx(3600.5)
    assert result.needs_transcode is False


def test_probe_media_raises_when_no_video_stream(monkeypatch):
    payload = {"format": {}, "streams": [{"codec_type": "audio", "codec_name": "aac"}]}
    monkeypatch.setattr(probe_mod, "_run_ffprobe", lambda path: payload)

    with pytest.raises(ProbeError):
        probe_media(Path("/games/audio-only.mp4"))


def test_probe_media_tolerates_missing_duration(monkeypatch):
    payload = {"format": {}, "streams": [{"codec_type": "video", "codec_name": "h264"}]}
    monkeypatch.setattr(probe_mod, "_run_ffprobe", lambda path: payload)

    result = probe_media(Path("/games/x.mp4"))
    assert result.duration_seconds is None
    assert result.audio_codec == ""


def test_probe_media_tolerates_non_numeric_duration(monkeypatch):
    # ffprobe occasionally reports "N/A"; the duration parse must not raise.
    payload = {
        "format": {"duration": "N/A"},
        "streams": [{"codec_type": "video", "codec_name": "h264"}],
    }
    monkeypatch.setattr(probe_mod, "_run_ffprobe", lambda path: payload)

    result = probe_media(Path("/games/x.mp4"))
    assert result.duration_seconds is None
