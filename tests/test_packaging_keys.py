"""Tests for the stable R2 key layout derivation."""

from __future__ import annotations

from pathlib import Path

import pytest

from archive.packaging.keys import (
    MANIFEST_NAME,
    derive_game_key,
    league_from_root,
    slugify_segment,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Ravens at Chiefs", "ravens-at-chiefs"),
        ("Week 1", "week-1"),
        ("  Trailing/Leading  ", "trailing-leading"),
        ("Multiple   spaces!!", "multiple-spaces"),
        ("2024", "2024"),
    ],
)
def test_slugify_segment(raw, expected):
    assert slugify_segment(raw) == expected


@pytest.mark.parametrize(
    ("root_name", "expected"),
    [
        ("NFL (1920)", "nfl"),
        ("NCAA (1939)", "ncaa"),
        ("UFL (2024)", "ufl"),
        ("CFL (1958)", "cfl"),
        ("PlainName", "plainname"),
    ],
)
def test_league_from_root(root_name, expected):
    assert league_from_root(Path(f"/mnt/g/{root_name}")) == expected


def test_derive_game_key_full_path():
    root = Path("/mnt/g/NFL (1920)")
    source = root / "2024" / "Week 1" / "Ravens at Chiefs.mp4"
    assert derive_game_key(root, source) == "nfl/2024/week-1/ravens-at-chiefs"


def test_derive_game_key_is_stable_and_extension_independent():
    root = Path("/mnt/g/UFL (2024)")
    mp4 = root / "Finals" / "Battlehawks vs Brahmas.mp4"
    mkv = root / "Finals" / "Battlehawks vs Brahmas.mkv"
    # Same game, different container -> same prefix (the manifest, not the
    # source extension, is what gets published).
    assert derive_game_key(root, mp4) == derive_game_key(root, mkv)
    assert derive_game_key(root, mp4) == "ufl/finals/battlehawks-vs-brahmas"


def test_derive_game_key_rejects_path_outside_root():
    root = Path("/mnt/g/NFL (1920)")
    with pytest.raises(ValueError):
        derive_game_key(root, Path("/mnt/g/UFL (2024)/x.mp4"))


def test_manifest_name_is_master_playlist():
    # ADR-0008 documents the manifest key as {game}/master.m3u8.
    assert MANIFEST_NAME == "master.m3u8"
