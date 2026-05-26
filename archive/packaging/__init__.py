"""Batch HLS packaging pipeline (TGF-362, ADR-0008).

Remuxes the static game-film catalog into CMAF/HLS and uploads it to
Cloudflare R2 under a stable, idempotent key layout. Entry point is the
``package_hls`` management command, which drives :class:`PackagingPipeline`.
"""

from .keys import MANIFEST_NAME, derive_game_key, league_from_root
from .packager import PackageResult, PackagingError, package_to_hls
from .pipeline import PackagingPipeline, PackagingSummary
from .probe import MediaProbe, ProbeError, probe_media
from .uploader import InMemoryUploader, R2Uploader, SyncResult, Uploader

__all__ = [
    "MANIFEST_NAME",
    "InMemoryUploader",
    "MediaProbe",
    "PackageResult",
    "PackagingError",
    "PackagingPipeline",
    "PackagingSummary",
    "ProbeError",
    "R2Uploader",
    "SyncResult",
    "Uploader",
    "derive_game_key",
    "league_from_root",
    "package_to_hls",
    "probe_media",
]
