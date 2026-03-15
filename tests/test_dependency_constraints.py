"""Tests to ensure griddy SDK dependency uses a bounded range, not an exact pin."""

import re
from pathlib import Path

PYPROJECT_PATH = Path(__file__).resolve().parents[1] / "pyproject.toml"


def test_griddy_dependency_is_not_exact_pin():
    """No consumer repo should pin an exact griddy version (TGF-218)."""
    content = PYPROJECT_PATH.read_text()
    match = re.search(r'"griddy([><=!~][^"]*)"', content)
    assert match is not None, "griddy dependency not found in pyproject.toml"
    version_spec = match.group(1)
    assert not version_spec.startswith("=="), (
        f"griddy must not use an exact version pin, found: griddy{version_spec}"
    )


def test_griddy_dependency_has_upper_bound():
    """The griddy range should have an upper bound to prevent major version surprises."""
    content = PYPROJECT_PATH.read_text()
    match = re.search(r'"griddy([><=!~][^"]*)"', content)
    assert match is not None, "griddy dependency not found in pyproject.toml"
    version_spec = match.group(1)
    assert "<" in version_spec, (
        f"griddy dependency should have an upper bound, found: griddy{version_spec}"
    )


def test_griddy_dependency_has_lower_bound():
    """The griddy range should have a lower bound at the minimum compatible version."""
    content = PYPROJECT_PATH.read_text()
    match = re.search(r'"griddy([><=!~][^"]*)"', content)
    assert match is not None, "griddy dependency not found in pyproject.toml"
    version_spec = match.group(1)
    assert ">=" in version_spec, (
        f"griddy dependency should have a lower bound, found: griddy{version_spec}"
    )
