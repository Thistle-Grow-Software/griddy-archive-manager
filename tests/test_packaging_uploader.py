"""Tests for the idempotent sync contract shared by all uploaders."""

from __future__ import annotations

from pathlib import Path

import pytest

from archive.packaging.uploader import (
    InMemoryUploader,
    WranglerLocalUploader,
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


class _RecordingRunner:
    """Captures the wrangler argv lists instead of executing them."""

    def __init__(self) -> None:
        self.calls: list[list[str]] = []

    def __call__(self, cmd) -> None:
        self.calls.append(list(cmd))


def test_wrangler_local_put_builds_command(tmp_path):
    manifest = tmp_path / "master.m3u8"
    manifest.write_text("#EXTM3U\n")
    runner = _RecordingRunner()
    uploader = WranglerLocalUploader(
        bucket="film", persist_to=".wrangler/state", runner=runner
    )

    written = uploader.put_file(
        "nfl/2024/game/master.m3u8", manifest, "application/vnd.apple.mpegurl"
    )

    assert written == len("#EXTM3U\n")
    assert runner.calls == [
        [
            "npx",
            "wrangler",
            "r2",
            "object",
            "put",
            "film/nfl/2024/game/master.m3u8",
            "--file",
            str(manifest),
            "--content-type",
            "application/vnd.apple.mpegurl",
            "--local",
            "--persist-to",
            ".wrangler/state",
        ]
    ]


def test_wrangler_local_sync_is_upload_only(tmp_path):
    bundle = _make_bundle(
        tmp_path / "bundle", segments=("seg_00000.m4s", "seg_00001.m4s")
    )
    runner = _RecordingRunner()
    uploader = WranglerLocalUploader(bucket="film", runner=runner)

    result = uploader.sync_dir("nfl/2024/game", bundle)

    # One `put` per file (init.mp4, master.m3u8, two segments); never lists/deletes.
    assert len(runner.calls) == 4
    assert all(call[4] == "put" for call in runner.calls)
    assert result.deleted_keys == []
    assert sorted(result.uploaded_keys) == [
        "nfl/2024/game/init.mp4",
        "nfl/2024/game/master.m3u8",
        "nfl/2024/game/seg_00000.m4s",
        "nfl/2024/game/seg_00001.m4s",
    ]


def test_wrangler_local_delete_keys_issues_commands():
    runner = _RecordingRunner()
    uploader = WranglerLocalUploader(bucket="film", runner=runner)

    uploader.delete_keys(["nfl/2024/game/seg_00099.m4s"])

    assert runner.calls == [
        [
            "npx",
            "wrangler",
            "r2",
            "object",
            "delete",
            "film/nfl/2024/game/seg_00099.m4s",
            "--local",
        ]
    ]


def test_wrangler_local_list_is_unsupported():
    uploader = WranglerLocalUploader(bucket="film", runner=_RecordingRunner())
    with pytest.raises(NotImplementedError):
        uploader.list_keys("nfl/2024/game")


def test_wrangler_local_sync_parallelizes_puts(tmp_path):
    """Sync issues puts concurrently up to max_workers and returns stable output."""
    import threading

    bundle = _make_bundle(
        tmp_path / "bundle",
        segments=tuple(f"seg_{i:05d}.m4s" for i in range(8)),
    )

    inflight = 0
    peak_inflight = 0
    lock = threading.Lock()

    def slow_runner(_cmd):
        nonlocal inflight, peak_inflight
        with lock:
            inflight += 1
            peak_inflight = max(peak_inflight, inflight)
        # Hold the call open long enough to overlap with siblings.
        threading.Event().wait(0.05)
        with lock:
            inflight -= 1

    uploader = WranglerLocalUploader(bucket="film", max_workers=4, runner=slow_runner)
    result = uploader.sync_dir("nfl/2024/game", bundle)

    # 10 files (manifest + init + 8 segments), every put issued, output stable.
    assert len(result.uploaded_keys) == 10
    assert result.uploaded_keys == sorted(result.uploaded_keys)
    assert peak_inflight > 1, "expected concurrent puts with max_workers=4"
    assert peak_inflight <= 4, "should not exceed configured max_workers"


def test_wrangler_local_max_workers_one_runs_sequentially(tmp_path):
    bundle = _make_bundle(tmp_path / "bundle", segments=("seg_00000.m4s",))
    runner = _RecordingRunner()
    uploader = WranglerLocalUploader(bucket="film", max_workers=1, runner=runner)

    result = uploader.sync_dir("nfl/2024/game", bundle)

    assert len(runner.calls) == 3  # master + init + 1 segment
    assert sorted(result.uploaded_keys) == result.uploaded_keys


class _FlakyRunner:
    """Fake runner that raises on the first ``fail_first`` calls, then succeeds."""

    def __init__(self, fail_first: int) -> None:
        self.calls: list[list[str]] = []
        self._fail_first = fail_first

    def __call__(self, cmd) -> None:
        self.calls.append(list(cmd))
        if len(self.calls) <= self._fail_first:
            raise RuntimeError(f"simulated transient failure {len(self.calls)}")


def test_wrangler_local_put_retries_transient_failures(tmp_path):
    payload = tmp_path / "a.bin"
    payload.write_bytes(b"data")
    runner = _FlakyRunner(fail_first=2)
    uploader = WranglerLocalUploader(
        bucket="film",
        max_attempts=3,
        retry_backoff_base=0,  # no sleep in tests
        runner=runner,
    )

    written = uploader.put_file("test/a", payload, "application/octet-stream")

    assert written == 4
    assert len(runner.calls) == 3  # 2 failures + 1 success


def test_wrangler_local_put_raises_after_exhausting_retries(tmp_path):
    payload = tmp_path / "a.bin"
    payload.write_bytes(b"data")
    runner = _FlakyRunner(fail_first=5)  # always fails within the attempt budget
    uploader = WranglerLocalUploader(
        bucket="film",
        max_attempts=3,
        retry_backoff_base=0,
        runner=runner,
    )

    with pytest.raises(RuntimeError, match="simulated transient failure"):
        uploader.put_file("test/a", payload, "application/octet-stream")
    assert len(runner.calls) == 3


def test_wrangler_local_max_attempts_one_disables_retries(tmp_path):
    payload = tmp_path / "a.bin"
    payload.write_bytes(b"data")
    runner = _FlakyRunner(fail_first=1)
    uploader = WranglerLocalUploader(
        bucket="film",
        max_attempts=1,
        retry_backoff_base=0,
        runner=runner,
    )

    with pytest.raises(RuntimeError):
        uploader.put_file("test/a", payload, "application/octet-stream")
    assert len(runner.calls) == 1  # no retry
