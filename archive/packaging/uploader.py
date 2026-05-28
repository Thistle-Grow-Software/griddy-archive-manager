"""Upload packaged HLS output to object storage, idempotently.

The :class:`Uploader` base class implements the idempotency contract once, in
:meth:`Uploader.sync_dir`: list everything already under a game's prefix, upload
the freshly packaged files (overwriting), then delete whatever was under the
prefix but is no longer part of the output. Re-packaging a game therefore leaves
no orphaned segments behind. Subclasses supply three primitives — list, put,
delete — so the same logic drives the real Cloudflare R2 backend
(:class:`R2Uploader`, S3-compatible via boto3) and the
:class:`InMemoryUploader` used in tests, with no network.
"""

from __future__ import annotations

import logging
import subprocess
from abc import ABC, abstractmethod
from collections.abc import Callable, Iterable, Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger("archive")

# Content types for the objects the packager emits. R2/S3 serve whatever is
# stored, and the player (hls.js) is content-type sensitive for the manifest.
_CONTENT_TYPES = {
    ".m3u8": "application/vnd.apple.mpegurl",
    ".m4s": "video/iso.segment",
    ".mp4": "video/mp4",
}
_DEFAULT_CONTENT_TYPE = "application/octet-stream"


def content_type_for(path: Path) -> str:
    return _CONTENT_TYPES.get(path.suffix.lower(), _DEFAULT_CONTENT_TYPE)


@dataclass(frozen=True)
class SyncResult:
    """What :meth:`Uploader.sync_dir` did for one prefix."""

    prefix: str
    uploaded_keys: list[str]
    deleted_keys: list[str]
    bytes_uploaded: int


def _iter_files(local_dir: Path) -> list[Path]:
    return sorted(p for p in local_dir.rglob("*") if p.is_file())


class Uploader(ABC):
    """Object-storage backend with an idempotent directory sync."""

    @abstractmethod
    def list_keys(self, prefix: str) -> set[str]:
        """Return every existing object key under ``prefix``."""

    @abstractmethod
    def put_file(self, key: str, local_path: Path, content_type: str) -> int:
        """Upload ``local_path`` to ``key``; return bytes written."""

    @abstractmethod
    def delete_keys(self, keys: Iterable[str]) -> None:
        """Delete the given object keys."""

    def sync_dir(self, prefix: str, local_dir: Path) -> SyncResult:
        """Mirror ``local_dir`` to ``prefix``, removing orphaned objects.

        Keys are ``{prefix}/{path-relative-to-local_dir}``. Existing objects are
        overwritten; any object under ``prefix`` not present in this upload is
        deleted so a re-run never leaves stale segments behind.
        """
        existing = self.list_keys(prefix)
        uploaded: list[str] = []
        bytes_uploaded = 0

        for path in _iter_files(local_dir):
            relative = path.relative_to(local_dir).as_posix()
            key = f"{prefix}/{relative}"
            bytes_uploaded += self.put_file(key, path, content_type_for(path))
            uploaded.append(key)

        orphans = sorted(existing - set(uploaded))
        if orphans:
            self.delete_keys(orphans)

        logger.debug(
            "synced %s: %d uploaded, %d deleted, %d bytes",
            prefix,
            len(uploaded),
            len(orphans),
            bytes_uploaded,
        )
        return SyncResult(
            prefix=prefix,
            uploaded_keys=uploaded,
            deleted_keys=orphans,
            bytes_uploaded=bytes_uploaded,
        )


class InMemoryUploader(Uploader):
    """In-memory backend for tests: records keys and their sizes."""

    def __init__(self) -> None:
        self.objects: dict[str, int] = {}

    def list_keys(self, prefix: str) -> set[str]:
        marker = f"{prefix}/"
        return {k for k in self.objects if k == prefix or k.startswith(marker)}

    def put_file(self, key: str, local_path: Path, content_type: str) -> int:
        size = local_path.stat().st_size
        self.objects[key] = size
        return size

    def delete_keys(self, keys: Iterable[str]) -> None:
        for key in keys:
            self.objects.pop(key, None)


class R2Uploader(Uploader):
    """Cloudflare R2 backend (S3-compatible) backed by boto3.

    boto3 is imported lazily so this module — and the packaging pipeline's unit
    tests — load without boto3 installed; it is only required to actually push
    to R2.
    """

    # R2 ignores the AWS region but boto3 requires one; "auto" is conventional.
    _REGION = "auto"
    # S3 deletes are capped at 1000 keys per request.
    _DELETE_BATCH = 1000

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str,
        access_key_id: str,
        secret_access_key: str,
    ) -> None:
        try:
            import boto3
        except ImportError as exc:  # pragma: no cover - exercised only without boto3
            raise RuntimeError(
                "boto3 is required to upload to R2; install it with `uv sync`"
            ) from exc

        self.bucket = bucket
        self._client = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key_id,
            aws_secret_access_key=secret_access_key,
            region_name=self._REGION,
        )

    def list_keys(self, prefix: str) -> set[str]:
        keys: set[str] = set()
        paginator = self._client.get_paginator("list_objects_v2")
        for page in paginator.paginate(Bucket=self.bucket, Prefix=f"{prefix}/"):
            for obj in page.get("Contents", []):
                keys.add(obj["Key"])
        return keys

    def put_file(self, key: str, local_path: Path, content_type: str) -> int:
        self._client.upload_file(
            str(local_path),
            self.bucket,
            key,
            ExtraArgs={"ContentType": content_type},
        )
        return local_path.stat().st_size

    def delete_keys(self, keys: Iterable[str]) -> None:
        batch = [{"Key": k} for k in keys]
        for start in range(0, len(batch), self._DELETE_BATCH):
            chunk = batch[start : start + self._DELETE_BATCH]
            self._client.delete_objects(Bucket=self.bucket, Delete={"Objects": chunk})


WranglerRunner = Callable[[Sequence[str]], None]


class WranglerLocalUploader(Uploader):
    """Local Miniflare R2 backend for the cost-free PoC (ADR-0008 / TGF-362).

    Loads packaged objects into the same local R2 store ``wrangler dev`` serves
    by shelling out to ``wrangler r2 object put ... --local``. This is the
    local-first path that lets the PoC run without provisioning real R2.

    The wrangler CLI exposes only ``get``/``put``/``delete`` for objects — there
    is no ``list`` (cloudflare/workers-sdk#13008) — so the base class's
    list-then-delete orphan sweep cannot run here. :meth:`sync_dir` is therefore
    **upload-only**: a ``put`` overwrites the object at a key, but re-packaging a
    game into *fewer* segments than a prior run may leave stale ones behind. For
    the static catalog that is rare and harmless for the PoC, and a prefix can be
    cleared by hand via :meth:`delete_keys`. The remote :class:`R2Uploader` keeps
    full idempotency for production (TGF-364).

    ``persist_to`` must match the directory ``wrangler dev`` uses or the Worker
    will not see the loaded objects (both default to ``.wrangler/state``).
    ``cwd`` runs wrangler from the Worker project directory so its config and
    persistence line up.

    ``max_workers`` parallelizes the per-object ``wrangler r2 object put``
    invocations across a thread pool; each invocation spawns its own Node
    process so wall-clock scales close to linearly with the worker count, and
    Miniflare's SQLite (in WAL mode) accepts concurrent writers. Set to ``1``
    for the sequential, debug-friendly behavior.
    """

    _DEFAULT_MAX_WORKERS = 8

    def __init__(
        self,
        *,
        bucket: str,
        persist_to: Path | str | None = None,
        command: Sequence[str] = ("npx", "wrangler"),
        cwd: Path | str | None = None,
        max_workers: int = _DEFAULT_MAX_WORKERS,
        runner: WranglerRunner | None = None,
    ) -> None:
        self.bucket = bucket
        self._persist_to = Path(persist_to) if persist_to else None
        self._command = list(command)
        self._cwd = Path(cwd) if cwd else None
        self._max_workers = max(1, max_workers)
        self._runner = runner or self._run_subprocess

    def _wrangler(self, *args: str) -> list[str]:
        cmd = [*self._command, "r2", "object", *args, "--local"]
        if self._persist_to is not None:
            cmd += ["--persist-to", str(self._persist_to)]
        return cmd

    def _run_subprocess(self, cmd: Sequence[str]) -> None:
        try:
            subprocess.run(
                list(cmd),
                capture_output=True,
                text=True,
                check=True,
                cwd=str(self._cwd) if self._cwd else None,
            )
        except FileNotFoundError as exc:  # pragma: no cover - environment-dependent
            raise RuntimeError(
                "wrangler executable not found; install it or pass --wrangler-cmd "
                "/ --wrangler-cwd pointing at the Worker project"
            ) from exc
        except subprocess.CalledProcessError as exc:  # pragma: no cover
            raise RuntimeError(f"wrangler failed: {exc.stderr}") from exc

    def list_keys(self, prefix: str) -> set[str]:
        raise NotImplementedError(
            "the wrangler CLI cannot list R2 objects "
            "(cloudflare/workers-sdk#13008); local sync is upload-only"
        )

    def put_file(self, key: str, local_path: Path, content_type: str) -> int:
        self._runner(
            self._wrangler(
                "put",
                f"{self.bucket}/{key}",
                "--file",
                str(local_path),
                "--content-type",
                content_type,
            )
        )
        return local_path.stat().st_size

    def delete_keys(self, keys: Iterable[str]) -> None:
        for key in keys:
            self._runner(self._wrangler("delete", f"{self.bucket}/{key}"))

    def sync_dir(self, prefix: str, local_dir: Path) -> SyncResult:
        """Upload every file under ``local_dir`` to ``prefix`` (upload-only).

        Unlike the base implementation this neither lists nor deletes — the
        wrangler CLI cannot enumerate objects, so orphan cleanup is skipped —
        and puts are issued in parallel across ``self._max_workers`` threads,
        since per-call Node spin-up dominates the wall-clock cost.
        """
        jobs = [
            (f"{prefix}/{path.relative_to(local_dir).as_posix()}", path)
            for path in _iter_files(local_dir)
        ]

        uploaded: list[str] = []
        bytes_uploaded = 0

        def _upload(job: tuple[str, Path]) -> tuple[str, int]:
            key, path = job
            return key, self.put_file(key, path, content_type_for(path))

        # Cap workers at the job count so the pool isn't oversized for small games.
        workers = min(self._max_workers, max(1, len(jobs)))
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_upload, job) for job in jobs]
            for future in as_completed(futures):
                key, written = future.result()
                uploaded.append(key)
                bytes_uploaded += written

        uploaded.sort()  # `as_completed` is non-deterministic; keep output stable.
        logger.debug(
            "loaded %s into local R2: %d objects, %d bytes (upload-only, %d workers)",
            prefix,
            len(uploaded),
            bytes_uploaded,
            workers,
        )
        return SyncResult(
            prefix=prefix,
            uploaded_keys=uploaded,
            deleted_keys=[],
            bytes_uploaded=bytes_uploaded,
        )
