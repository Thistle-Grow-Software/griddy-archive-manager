"""``poc_load_game`` — load one packaged game into the local R2 store for the PoC.

The end-to-end PoC (TGF-363, ADR-0008) needs a real game playable through the
local Worker. The Worker serves objects by request path, and the playback API
(TGF-360) mints URLs of the form ``/games/{id}/master.m3u8`` — so this command
packages a single source file to CMAF/HLS and loads it into the local Miniflare
R2 store under the matching ``games/{id}/`` prefix (rather than the slugified
catalog prefix the batch ``package_hls`` uses).

It also records measurements (packaged size, segment count, ratio, duration) to
a JSON file so the cost model (``scripts/video_cost_model.py``) can be driven
from a real local measurement instead of guesses, satisfying the "projected from
local measurements" acceptance criterion. With ``--mint-token`` it prints the
signed playback URL the player page / Playwright spec can load.

Example::

    uv run manage.py poc_load_game \\
        "/mnt/g/NFL (1920)/NFL Condensed Games (1920)/Season 2025/<game>.mp4" \\
        --game-id 2025001 --wrangler-cwd video-worker \\
        --measurements-out docs/video-poc/measurements.json --mint-token
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from archive.packaging.keys import MANIFEST_NAME
from archive.packaging.packager import DEFAULT_SEGMENT_DURATION, package_to_hls
from archive.packaging.probe import ProbeError, probe_media
from archive.packaging.uploader import WranglerLocalUploader


class Command(BaseCommand):
    help = (
        "Package one game to HLS and load it into the local R2 store under games/{id}/."
    )

    def add_arguments(self, parser) -> None:
        parser.add_argument("source", help="Path to the source video file.")
        parser.add_argument(
            "--game-id",
            required=True,
            help="Game id; objects load under games/{id}/ to match the playback URL.",
        )
        parser.add_argument(
            "--bucket",
            default="griddy-video",
            help="Local R2 bucket name (default griddy-video).",
        )
        parser.add_argument(
            "--persist-to",
            default=None,
            help="Miniflare persistence dir; must match `wrangler dev` (default .wrangler/state).",
        )
        parser.add_argument(
            "--wrangler-cwd",
            default="video-worker",
            help="Directory to run wrangler from — the Worker project (default video-worker).",
        )
        parser.add_argument(
            "--segment-duration",
            type=int,
            default=DEFAULT_SEGMENT_DURATION,
            help=f"HLS target segment length in seconds (default {DEFAULT_SEGMENT_DURATION}).",
        )
        parser.add_argument(
            "--measurements-out",
            default=None,
            help="Write packaged-size/segment-count measurements to this JSON path.",
        )
        parser.add_argument(
            "--mint-token",
            action="store_true",
            help="Also mint a playback token and print the local playback URL.",
        )

    def handle(self, *args, **options) -> None:
        source = Path(options["source"])
        if not source.is_file():
            raise CommandError(f"Source file not found: {source}")
        game_id: str = str(options["game_id"])
        segment_duration: int = options["segment_duration"]
        if segment_duration <= 0:
            raise CommandError("--segment-duration must be a positive integer.")

        try:
            probe = probe_media(source)
        except ProbeError as exc:
            raise CommandError(str(exc)) from exc

        self.stdout.write(
            f"Packaging {source.name} "
            f"(video={probe.video_codec}, audio={probe.audio_codec or 'none'}, "
            f"{'transcode' if probe.needs_transcode else 'copy'})…"
        )

        with tempfile.TemporaryDirectory(prefix="poc-hls-") as tmp:
            out_dir = Path(tmp)
            result = package_to_hls(
                source, out_dir, probe, segment_duration=segment_duration
            )
            segment_count = len(result.segment_paths)
            source_bytes = source.stat().st_size

            prefix = f"games/{game_id}"
            self.stdout.write(
                f"Loading {segment_count} segments + manifest into "
                f"{options['bucket']}/{prefix}/ via local R2…"
            )
            uploader = WranglerLocalUploader(
                bucket=options["bucket"],
                persist_to=options["persist_to"],
                cwd=options["wrangler_cwd"],
            )
            sync = uploader.sync_dir(prefix, out_dir)

        measurements = {
            "game_id": game_id,
            "source_name": source.name,
            "source_bytes": source_bytes,
            "output_bytes": result.output_bytes,
            "size_ratio": (
                result.output_bytes / source_bytes if source_bytes else None
            ),
            "segment_count": segment_count,
            "segment_duration_seconds": segment_duration,
            "duration_seconds": probe.duration_seconds,
            "transcoded": result.transcoded,
            "manifest_key": f"{prefix}/{MANIFEST_NAME}",
            "objects_loaded": len(sync.uploaded_keys),
            "bytes_loaded": sync.bytes_uploaded,
        }

        self._report(measurements)

        if options["measurements_out"]:
            out_path = Path(options["measurements_out"])
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(json.dumps(measurements, indent=2), encoding="utf-8")
            self.stdout.write(self.style.SUCCESS(f"Wrote measurements to {out_path}"))

        if options["mint_token"]:
            self._print_playback_url(game_id)

    def _report(self, m: dict) -> None:
        ratio = m["size_ratio"]
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Loaded one game into local R2"))
        self.stdout.write(f"  manifest key   : {m['manifest_key']}")
        self.stdout.write(f"  segments       : {m['segment_count']}")
        self.stdout.write(f"  source bytes   : {m['source_bytes']:,}")
        self.stdout.write(
            f"  output bytes   : {m['output_bytes']:,}"
            + (f" ({ratio:.2f}x source)" if ratio else "")
        )
        dur = m["duration_seconds"]
        if dur:
            self.stdout.write(f"  duration       : {dur / 60:.1f} min")

    def _print_playback_url(self, game_id: str) -> None:
        from django.conf import settings

        from gam.playback.tokens import mint_playback_token

        minted = mint_playback_token(subject="poc-user", game_id=game_id)
        origin = settings.VIDEO_ORIGIN_URL.rstrip("/")
        url = f"{origin}/games/{game_id}/{MANIFEST_NAME}?t={minted.token}"
        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Playback URL (token expires soon):"))
        self.stdout.write(f"  {url}")
        self.stdout.write(f"  expires_at: {minted.expires_at.isoformat()}")
