"""``package_hls`` — batch-remux the game-film catalog to CMAF/HLS on R2.

Implements the one-time batch packaging from ADR-0008 (TGF-362). Walks the
league source trees, packages each game to fragmented-MP4 + an HLS manifest at
a ~6s target (lossless stream copy for the H.264/AAC majority, transcode for
the handful of VP9/AV1/HEVC/Opus/AC-3 outliers), and uploads each game to a
stable, idempotent R2 prefix.

Examples::

    # Package the four roots configured in HLS_SOURCE_ROOTS and upload to R2.
    uvrm package_hls

    # Package explicit roots, one game per league, without uploading.
    uvrm package_hls "/mnt/g/NFL (1920)" "/mnt/g/UFL (2024)" \\
        --limit-per-league 1 --dry-run
"""

from __future__ import annotations

import shlex
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from archive.packaging import PackagingPipeline
from archive.packaging.packager import DEFAULT_SEGMENT_DURATION
from archive.packaging.uploader import (
    InMemoryUploader,
    R2Uploader,
    WranglerLocalUploader,
)


class Command(BaseCommand):
    help = "Batch-package the game-film catalog to CMAF/HLS and upload to R2."

    def add_arguments(self, parser) -> None:
        parser.add_argument(
            "roots",
            nargs="*",
            help=(
                "League source directories to walk. Defaults to "
                "settings.HLS_SOURCE_ROOTS."
            ),
        )
        parser.add_argument(
            "--segment-duration",
            type=int,
            default=DEFAULT_SEGMENT_DURATION,
            help=f"HLS target segment length in seconds (default {DEFAULT_SEGMENT_DURATION}).",
        )
        parser.add_argument(
            "--limit-per-league",
            type=int,
            default=None,
            help=(
                "Package at most N files per source root. Useful for validating "
                "one game per league before a full run."
            ),
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Probe and package locally but upload nothing to R2.",
        )
        parser.add_argument(
            "--local",
            action="store_true",
            help=(
                "Load packaged output into the local Miniflare R2 store via "
                "`wrangler r2 object put --local` (the cost-free PoC path, "
                "ADR-0008) instead of uploading to real R2."
            ),
        )
        parser.add_argument(
            "--bucket",
            default=None,
            help="R2 bucket name for --local (defaults to settings.R2_BUCKET).",
        )
        parser.add_argument(
            "--persist-to",
            default=None,
            help=(
                "Miniflare persistence directory for --local. Must match the "
                "`wrangler dev --persist-to` value (default .wrangler/state)."
            ),
        )
        parser.add_argument(
            "--wrangler-cmd",
            default="npx wrangler",
            help='Command used to invoke wrangler for --local (default "npx wrangler").',
        )
        parser.add_argument(
            "--wrangler-cwd",
            default=None,
            help=(
                "Directory to run wrangler from for --local — the Worker project "
                "(TGF-361) — so its config and local persistence align."
            ),
        )

    def handle(self, *args, **options) -> None:
        roots = self._resolve_roots(options["roots"])
        dry_run: bool = options["dry_run"]
        local: bool = options["local"]
        segment_duration: int = options["segment_duration"]
        if segment_duration <= 0:
            raise CommandError("--segment-duration must be a positive integer.")
        if dry_run and local:
            raise CommandError("--dry-run and --local are mutually exclusive.")

        if dry_run:
            uploader = InMemoryUploader()
            target = "dry run, no upload"
        elif local:
            uploader = self._build_local_uploader(options)
            target = "loading into local R2 (Miniflare)"
        else:
            uploader = self._build_r2_uploader()
            target = "uploading to R2"

        self.stdout.write(f"Packaging {len(roots)} root(s) ({target})…")
        pipeline = PackagingPipeline(
            uploader, segment_duration=segment_duration, dry_run=dry_run
        )
        summary = pipeline.run(roots, limit_per_root=options["limit_per_league"])

        self._report(summary, dry_run=dry_run)

    def _resolve_roots(self, raw_roots: list[str]) -> list[Path]:
        raw = raw_roots or list(settings.HLS_SOURCE_ROOTS)
        if not raw:
            raise CommandError(
                "No source roots given and HLS_SOURCE_ROOTS is unset. Pass roots "
                "as positional arguments or set the HLS_SOURCE_ROOTS env var."
            )
        return [Path(r) for r in raw]

    def _build_r2_uploader(self) -> R2Uploader:
        missing = [
            name
            for name in (
                "R2_BUCKET",
                "R2_ENDPOINT_URL",
                "R2_ACCESS_KEY_ID",
                "R2_SECRET_ACCESS_KEY",
            )
            if not getattr(settings, name, None)
        ]
        if missing:
            raise CommandError(
                "Missing R2 configuration: "
                + ", ".join(missing)
                + ". Set them in the environment or use --dry-run."
            )
        return R2Uploader(
            bucket=settings.R2_BUCKET,
            endpoint_url=settings.R2_ENDPOINT_URL,
            access_key_id=settings.R2_ACCESS_KEY_ID,
            secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        )

    def _build_local_uploader(self, options) -> WranglerLocalUploader:
        bucket = options["bucket"] or getattr(settings, "R2_BUCKET", None)
        if not bucket:
            raise CommandError(
                "--local needs a bucket name; pass --bucket or set R2_BUCKET."
            )
        return WranglerLocalUploader(
            bucket=bucket,
            persist_to=options["persist_to"],
            command=shlex.split(options["wrangler_cmd"]),
            cwd=options["wrangler_cwd"],
        )

    def _report(self, summary, *, dry_run: bool) -> None:
        ratio = summary.size_ratio
        ratio_str = f"{ratio:.2f}x source" if ratio is not None else "n/a"
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Packaging summary"))
        self.stdout.write(f"  files processed : {summary.files_processed}")
        self.stdout.write(f"  copied (remux)  : {summary.copied}")
        self.stdout.write(f"  transcoded      : {summary.transcoded}")
        self.stdout.write(f"  failed          : {summary.failed}")
        self.stdout.write(f"  source bytes    : {summary.source_bytes}")
        self.stdout.write(f"  output bytes    : {summary.output_bytes} ({ratio_str})")
        if not dry_run:
            self.stdout.write(f"  bytes uploaded  : {summary.bytes_uploaded}")

        if not summary.within_budget:
            self.stdout.write(
                self.style.WARNING(
                    f"  WARNING: output is {ratio_str}, above the 1.5x budget."
                )
            )
        for failure in summary.failures:
            self.stdout.write(
                self.style.ERROR(f"  FAILED: {failure.path}: {failure.error}")
            )
        if summary.failed:
            raise CommandError(
                f"{summary.failed} file(s) failed to package; see log for details."
            )
