"""Tests for the idempotent sync contract shared by all uploaders."""

from __future__ import annotations

from pathlib import Path

from archive.packaging.uploader import (
    InMemoryUploader,
    content_type_for,
)


def _make_bundle(root: Path, segments=("seg_00000.m4s",)) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    (root / "master.m3u8").write_text("#EXTM3U\n")
    (root / "init.mp4").write_bytes(b"init")
    for name in segments:
        (root / name).write_bytes(b"x" * 10)
    return root


def test_content_type_mapping():
    assert content_type_for(Path("a/master.m3u8")) == "application/vnd.apple.mpegurl"
    assert content_type_for(Path("a/seg_1.m4s")) == "video/iso.segment"
    assert content_type_for(Path("a/init.mp4")) == "video/mp4"
    assert content_type_for(Path("a/weird.xyz")) == "application/octet-stream"


def test_sync_dir_uploads_under_prefix(tmp_path):
    bundle = _make_bundle(tmp_path / "bundle")
    uploader = InMemoryUploader()

    result = uploader.sync_dir("nfl/2024/game", bundle)

    assert set(uploader.objects) == {
        "nfl/2024/game/master.m3u8",
        "nfl/2024/game/init.mp4",
        "nfl/2024/game/seg_00000.m4s",
    }
    assert result.bytes_uploaded == len("#EXTM3U\n") + len(b"init") + 10
    assert result.deleted_keys == []


def test_sync_dir_is_idempotent_and_removes_orphans(tmp_path):
    uploader = InMemoryUploader()

    # First run: a two-segment game.
    first = _make_bundle(tmp_path / "v1", segments=("seg_00000.m4s", "seg_00001.m4s"))
    uploader.sync_dir("nfl/2024/game", first)
    assert "nfl/2024/game/seg_00001.m4s" in uploader.objects

    # Re-package the same game, now only one segment (e.g. a shorter re-encode).
    second = _make_bundle(tmp_path / "v2", segments=("seg_00000.m4s",))
    result = uploader.sync_dir("nfl/2024/game", second)

    # The stale second segment is gone; no orphans remain under the prefix.
    assert "nfl/2024/game/seg_00001.m4s" not in uploader.objects
    assert result.deleted_keys == ["nfl/2024/game/seg_00001.m4s"]
    assert set(uploader.objects) == {
        "nfl/2024/game/master.m3u8",
        "nfl/2024/game/init.mp4",
        "nfl/2024/game/seg_00000.m4s",
    }


def test_sync_dir_does_not_touch_other_games(tmp_path):
    uploader = InMemoryUploader()
    uploader.sync_dir("nfl/2024/game-a", _make_bundle(tmp_path / "a"))
    uploader.sync_dir("nfl/2024/game-b", _make_bundle(tmp_path / "b"))

    # Re-syncing game-a must leave game-b untouched even though both share the
    # "nfl/2024/" ancestry (prefix matching is boundary-aware).
    uploader.sync_dir("nfl/2024/game-a", _make_bundle(tmp_path / "a2"))
    assert any(k.startswith("nfl/2024/game-b/") for k in uploader.objects)
