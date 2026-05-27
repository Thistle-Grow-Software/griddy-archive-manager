"""Derive the stable R2 key layout for a packaged game.

Every object for one game lives under a single prefix so the pipeline can be
idempotent — re-packaging a game lists that prefix, overwrites what it
re-uploads, and deletes anything left behind (see ``uploader.sync_dir``). The
prefix is derived deterministically from the source path, so the same file
always maps to the same prefix:

    {league}/{relative-path-of-the-file-without-extension, slugified}/

where ``{league}`` comes from the scanned root directory name (``NFL (1920)``
-> ``nfl``) and the remaining segments mirror the file's location under that
root. For a source file::

    /mnt/g/NFL (1920)/2024/Week 1/Ravens at Chiefs.mp4

scanned with root ``/mnt/g/NFL (1920)`` the prefix is::

    nfl/2024/week-1/ravens-at-chiefs

and the published manifest is ``nfl/2024/week-1/ravens-at-chiefs/master.m3u8``.
"""

from __future__ import annotations

import re
from pathlib import Path

# The published HLS manifest filename, the entry point the playback endpoint
# (ADR-0008) hands back to the player.
MANIFEST_NAME = "master.m3u8"

_SLUG_STRIP = re.compile(r"[^a-z0-9]+")
# Trailing " (1920)" style year/era suffix on a league root directory name.
_LEAGUE_SUFFIX = re.compile(r"\s*\(.*\)\s*$")


def slugify_segment(value: str) -> str:
    """Lowercase, collapse runs of non-alphanumerics to single hyphens."""
    return _SLUG_STRIP.sub("-", value.lower()).strip("-")


def league_from_root(root: Path) -> str:
    """Slugged league name from a scanned root, e.g. ``NFL (1920)`` -> ``nfl``."""
    return slugify_segment(_LEAGUE_SUFFIX.sub("", root.name))


def derive_game_key(root: Path, source: Path) -> str:
    """Return the stable, slash-joined key prefix for ``source`` under ``root``.

    ``source`` must be inside ``root``. The file extension is dropped and every
    path segment is slugified, guaranteeing a key safe for object storage and
    stable across runs. Empty segments (after slugifying) are skipped so odd
    directory names cannot produce ``//`` in the key.
    """
    relative = source.relative_to(root).with_suffix("")
    segments = [league_from_root(root)]
    segments.extend(slugify_segment(part) for part in relative.parts)
    return "/".join(seg for seg in segments if seg)
