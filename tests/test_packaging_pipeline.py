"""Tests for the batch orchestration: walking, counting, error isolation."""

from __future__ import annotations

from pathlib import Path

import pytest

from archive.packaging import pipeline as pipeline_mod
from archive.packaging.packager import PackageResult
from archive.packaging.pipeline import PackagingPipeline
from archive.packaging.probe import MediaProbe, ProbeError
from archive.packaging.uploader import InMemoryUploader

OUTPUT_BYTES = 107  # manifest + one segment in the fake packager


def _write_video(path: Path, size: int = 1000) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"v" * size)
    return path


def _fake_probe(path: Path) -> MediaProbe:
    # Codec inferred from the filename so tests can mix copy/transcode cases.
    if "vp9" in path.name or "av1" in path.name:
        return MediaProbe(path, "vp9", "aac", 10.0)
    return MediaProbe(path, "h264", "aac", 10.0)


def _fake_package(source, out_dir, probe, *, segment_duration):
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "master.m3u8").write_text("#EXTM3U\n")
    (out_dir / "seg_00000.m4s").write_bytes(b"x" * 100)
    return PackageResult(
        manifest_path=out_dir / "master.m3u8",
        segment_paths=[out_dir / "seg_00000.m4s"],
        output_bytes=OUTPUT_BYTES,
        transcoded=probe.needs_transcode,
    )


@pytest.fixture
def patched(monkeypatch):
    monkeypatch.setattr(pipeline_mod, "probe_media", _fake_probe)
    monkeypatch.setattr(pipeline_mod, "package_to_hls", _fake_package)


def test_run_packages_and_uploads_all_games(tmp_path, patched):
    root = tmp_path / "NFL (1920)"
    _write_video(root / "2024" / "game-a.mp4")
    _write_video(root / "2024" / "game-b.mp4")
    _write_video(root / "2024" / "game-vp9.mp4")
    _write_video(root / "notes.txt")  # ignored: not a video extension

    uploader = InMemoryUploader()
    summary = PackagingPipeline(uploader).run([root])

    assert summary.files_processed == 3
    assert summary.copied == 2
    assert summary.transcoded == 1
    assert summary.failed == 0
    assert summary.output_bytes == 3 * OUTPUT_BYTES
    # Each game produced a manifest under its own slugged prefix.
    assert "nfl/2024/game-a/master.m3u8" in uploader.objects
    assert "nfl/2024/game-vp9/master.m3u8" in uploader.objects
    assert summary.bytes_uploaded > 0


def test_size_ratio_and_budget(tmp_path, patched):
    root = tmp_path / "UFL (2024)"
    _write_video(root / "g.mp4", size=OUTPUT_BYTES)  # output == source -> 1.0x
    summary = PackagingPipeline(InMemoryUploader()).run([root])
    assert summary.size_ratio == pytest.approx(1.0)
    assert summary.within_budget is True


def test_one_bad_file_does_not_abort_the_batch(tmp_path, monkeypatch):
    root = tmp_path / "NFL (1920)"
    _write_video(root / "good.mp4")
    _write_video(root / "bad.mp4")

    def flaky_probe(path: Path) -> MediaProbe:
        if path.name == "bad.mp4":
            raise ProbeError("boom")
        return _fake_probe(path)

    monkeypatch.setattr(pipeline_mod, "probe_media", flaky_probe)
    monkeypatch.setattr(pipeline_mod, "package_to_hls", _fake_package)

    summary = PackagingPipeline(InMemoryUploader()).run([root])

    assert summary.files_processed == 1
    assert summary.failed == 1
    assert summary.failures[0].path.name == "bad.mp4"
    assert "boom" in summary.failures[0].error


def test_limit_per_root(tmp_path, patched):
    root = tmp_path / "NFL (1920)"
    for i in range(5):
        _write_video(root / f"game-{i}.mp4")

    summary = PackagingPipeline(InMemoryUploader()).run([root], limit_per_root=2)
    assert summary.files_processed == 2


def test_dry_run_packages_without_uploading(tmp_path, patched):
    root = tmp_path / "NFL (1920)"
    _write_video(root / "game.mp4")

    uploader = InMemoryUploader()
    summary = PackagingPipeline(uploader, dry_run=True).run([root])

    assert summary.files_processed == 1
    assert summary.bytes_uploaded == 0
    assert uploader.objects == {}


def test_missing_root_is_skipped_with_warning(tmp_path, patched):
    summary = PackagingPipeline(InMemoryUploader()).run([tmp_path / "does-not-exist"])
    assert summary.files_processed == 0
    assert summary.failed == 0
