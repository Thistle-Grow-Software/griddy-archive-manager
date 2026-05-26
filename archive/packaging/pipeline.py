"""Walk the source trees, package each game, and upload to R2.

This is the orchestration layer for the one-time batch packaging job from
ADR-0008. It ties together :mod:`probe`, :mod:`packager`, :mod:`keys`, and
:mod:`uploader`: for every video file under each league root it probes codecs,
packages to a temporary CMAF/HLS bundle, and syncs that bundle to the file's
stable R2 prefix. Failures on one file are logged and counted but never abort
the batch, and a :class:`PackagingSummary` records the copied/transcoded counts
and byte totals the job reports on completion.
"""

from __future__ import annotations

import logging
import tempfile
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from . import keys as keys_mod
from .packager import DEFAULT_SEGMENT_DURATION, package_to_hls
from .probe import probe_media
from .uploader import Uploader

logger = logging.getLogger("archive")

# Container extensions worth probing. Mirrors the catalog scanner's set; the
# archive is overwhelmingly .mp4 with a couple of .ts.
VIDEO_EXTS = {
    ".mp4",
    ".mkv",
    ".mov",
    ".m4v",
    ".ts",
    ".m2ts",
    ".webm",
    ".avi",
    ".wmv",
    ".mpg",
    ".mpeg",
}

# Output that is more than this multiple of the source is flagged in the summary
# (ADR-0008 budgets ~1x for remux; AC ceiling is ~1.5x).
SIZE_RATIO_CEILING = 1.5


@dataclass
class FailedFile:
    path: Path
    error: str


@dataclass
class PackagingSummary:
    """Tallies for one run of the pipeline, logged on completion."""

    files_processed: int = 0
    copied: int = 0
    transcoded: int = 0
    source_bytes: int = 0
    output_bytes: int = 0
    bytes_uploaded: int = 0
    failures: list[FailedFile] = field(default_factory=list)

    @property
    def failed(self) -> int:
        return len(self.failures)

    @property
    def size_ratio(self) -> float | None:
        if self.source_bytes == 0:
            return None
        return self.output_bytes / self.source_bytes

    @property
    def within_budget(self) -> bool:
        ratio = self.size_ratio
        return ratio is None or ratio <= SIZE_RATIO_CEILING


class PackagingPipeline:
    """Package every game under the given roots and upload to ``uploader``.

    ``uploader`` is the destination backend. When ``dry_run`` is set, files are
    still probed and packaged (so the work is exercised locally) but nothing is
    uploaded — useful for validating output before committing storage.
    """

    def __init__(
        self,
        uploader: Uploader,
        *,
        segment_duration: int = DEFAULT_SEGMENT_DURATION,
        dry_run: bool = False,
    ) -> None:
        self._uploader = uploader
        self._segment_duration = segment_duration
        self._dry_run = dry_run

    def iter_source_files(self, root: Path) -> Iterator[Path]:
        """Yield packageable video files under ``root`` in deterministic order."""
        for path in sorted(root.rglob("*")):
            if path.is_file() and path.suffix.lower() in VIDEO_EXTS:
                yield path

    def run(
        self, roots: list[Path], *, limit_per_root: int | None = None
    ) -> PackagingSummary:
        summary = PackagingSummary()
        for root in roots:
            if not root.is_dir():
                logger.warning("not a directory, skipping: %s", root)
                continue
            for processed_here, source in enumerate(self.iter_source_files(root)):
                if limit_per_root is not None and processed_here >= limit_per_root:
                    break
                self._process_file(root, source, summary)
        self._log_summary(summary)
        return summary

    def _process_file(
        self, root: Path, source: Path, summary: PackagingSummary
    ) -> None:
        try:
            probe = probe_media(source)
            key_prefix = keys_mod.derive_game_key(root, source)
            with tempfile.TemporaryDirectory(prefix="hls_") as tmp:
                result = package_to_hls(
                    source,
                    Path(tmp),
                    probe,
                    segment_duration=self._segment_duration,
                )
                if not self._dry_run:
                    sync = self._uploader.sync_dir(key_prefix, Path(tmp))
                    summary.bytes_uploaded += sync.bytes_uploaded
        except Exception as exc:  # isolate one file's failure from the batch
            logger.exception("failed to package %s", source)
            summary.failures.append(FailedFile(path=source, error=str(exc)))
            return

        summary.files_processed += 1
        summary.source_bytes += source.stat().st_size
        summary.output_bytes += result.output_bytes
        if result.transcoded:
            summary.transcoded += 1
        else:
            summary.copied += 1

    def _log_summary(self, summary: PackagingSummary) -> None:
        ratio = summary.size_ratio
        ratio_str = f"{ratio:.2f}x" if ratio is not None else "n/a"
        logger.info(
            "packaging complete: %d processed (%d copied, %d transcoded), "
            "%d failed; source=%d B, output=%d B (%s), uploaded=%d B",
            summary.files_processed,
            summary.copied,
            summary.transcoded,
            summary.failed,
            summary.source_bytes,
            summary.output_bytes,
            ratio_str,
            summary.bytes_uploaded,
        )
        if not summary.within_budget:
            logger.warning(
                "packaged output is %s of source, above the %.1fx budget",
                ratio_str,
                SIZE_RATIO_CEILING,
            )
