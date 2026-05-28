"""Tests for the ``package_hls`` management command wiring."""

from __future__ import annotations

from io import StringIO
from pathlib import Path

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from archive.packaging import pipeline as pipeline_mod
from archive.packaging.packager import PackageResult
from archive.packaging.probe import MediaProbe


def _fake_probe(path: Path) -> MediaProbe:
    return MediaProbe(path, "h264", "aac", 10.0)


def _fake_package(source, out_dir, probe, *, segment_duration):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "master.m3u8").write_text("#EXTM3U\n")
    return PackageResult(out_dir / "master.m3u8", [], 8, probe.needs_transcode)


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(pipeline_mod, "probe_media", _fake_probe)
    monkeypatch.setattr(pipeline_mod, "package_to_hls", _fake_package)


def test_dry_run_reports_summary(tmp_path, patched):
    root = tmp_path / "NFL (1920)"
    root.mkdir()
    (root / "game.mp4").write_bytes(b"v" * 50)

    out = StringIO()
    call_command("package_hls", str(root), "--dry-run", stdout=out)

    text = out.getvalue()
    assert "Packaging summary" in text
    assert "files processed : 1" in text


def test_errors_when_no_roots_configured(settings):
    settings.HLS_SOURCE_ROOTS = []
    with pytest.raises(CommandError, match="No source roots"):
        call_command("package_hls", "--dry-run")


def test_uses_configured_default_roots(tmp_path, patched, settings):
    root = tmp_path / "CFL (1958)"
    root.mkdir()
    (root / "game.mp4").write_bytes(b"v" * 50)
    settings.HLS_SOURCE_ROOTS = [str(root)]

    out = StringIO()
    call_command("package_hls", "--dry-run", stdout=out)
    assert "files processed : 1" in out.getvalue()


def test_errors_on_missing_r2_config_for_real_upload(tmp_path, settings):
    root = tmp_path / "NFL (1920)"
    root.mkdir()
    settings.R2_BUCKET = None
    settings.R2_ENDPOINT_URL = None
    settings.R2_ACCESS_KEY_ID = None
    settings.R2_SECRET_ACCESS_KEY = None

    with pytest.raises(CommandError, match="Missing R2 configuration"):
        call_command("package_hls", str(root))


def test_builds_r2_uploader_when_configured(tmp_path, settings):
    # Empty root -> zero files -> no network calls, but the R2 uploader (and its
    # boto3 client) is still constructed, exercising the non-dry-run path.
    root = tmp_path / "NFL (1920)"
    root.mkdir()
    settings.R2_BUCKET = "griddy-video"
    settings.R2_ENDPOINT_URL = "https://acct.r2.cloudflarestorage.com"
    settings.R2_ACCESS_KEY_ID = "key"
    settings.R2_SECRET_ACCESS_KEY = "secret"

    out = StringIO()
    call_command("package_hls", str(root), stdout=out)
    assert "files processed : 0" in out.getvalue()


def test_rejects_non_positive_segment_duration(tmp_path, settings):
    root = tmp_path / "NFL (1920)"
    root.mkdir()
    with pytest.raises(CommandError, match="segment-duration"):
        call_command("package_hls", str(root), "--dry-run", "--segment-duration", "0")


def test_local_and_dry_run_are_mutually_exclusive(tmp_path):
    root = tmp_path / "NFL (1920)"
    root.mkdir()
    with pytest.raises(CommandError, match="mutually exclusive"):
        call_command(
            "package_hls", str(root), "--dry-run", "--local", "--bucket", "film"
        )


def test_local_requires_a_bucket(tmp_path, settings):
    root = tmp_path / "NFL (1920)"
    root.mkdir()
    settings.R2_BUCKET = None
    with pytest.raises(CommandError, match="needs a bucket name"):
        call_command("package_hls", str(root), "--local")


def test_builds_local_uploader_when_bucket_given(tmp_path, patched):
    # Empty root -> zero files -> no wrangler is ever invoked, but the local
    # uploader is constructed, exercising the --local wiring without the CLI.
    root = tmp_path / "NFL (1920)"
    root.mkdir()

    out = StringIO()
    call_command("package_hls", str(root), "--local", "--bucket", "film", stdout=out)
    assert "files processed : 0" in out.getvalue()
    assert "local R2 (Miniflare)" in out.getvalue()


def test_dry_run_emits_per_file_progress(tmp_path, patched):
    """Each source file gets a [i/N] packaging line so runs aren't silent."""
    root = tmp_path / "NFL (1920)"
    root.mkdir()
    (root / "game-a.mp4").write_bytes(b"v" * 50)
    (root / "game-b.mp4").write_bytes(b"v" * 50)

    out = StringIO()
    call_command("package_hls", str(root), "--dry-run", stdout=out)

    text = out.getvalue()
    assert "[1/2] packaging game-a.mp4" in text
    assert "[2/2] packaging game-b.mp4" in text
