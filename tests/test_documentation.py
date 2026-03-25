"""Tests to ensure documentation infrastructure is correctly configured."""

from pathlib import Path

import tomllib

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DOCS_DIR = PROJECT_ROOT / "docs"
ZENSICAL_TOML = PROJECT_ROOT / "zensical.toml"
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"


def test_zensical_toml_exists():
    """zensical.toml must exist in the project root."""
    assert ZENSICAL_TOML.exists(), "zensical.toml not found in project root"


def test_zensical_toml_is_valid():
    """zensical.toml must be valid TOML."""
    config = tomllib.loads(ZENSICAL_TOML.read_text())
    assert "project" in config, "zensical.toml missing [project] section"


def test_zensical_toml_has_mkdocstrings():
    """zensical.toml must configure mkdocstrings plugin."""
    config = tomllib.loads(ZENSICAL_TOML.read_text())
    plugins = config["project"].get("plugins", {})
    assert "mkdocstrings" in plugins, "mkdocstrings plugin not configured in zensical.toml"


def test_zensical_toml_has_material_theme():
    """zensical.toml must configure a theme with palette (Material theme)."""
    config = tomllib.loads(ZENSICAL_TOML.read_text())
    theme = config["project"].get("theme", {})
    assert "palette" in theme, "Theme palette not configured in zensical.toml"


def test_docs_directory_exists():
    """A docs/ directory must exist."""
    assert DOCS_DIR.is_dir(), "docs/ directory not found"


def test_required_doc_pages_exist():
    """All nav-referenced doc pages must exist."""
    required_pages = [
        "index.md",
        "getting-started.md",
        "architecture.md",
        "commands.md",
        "reference/index.md",
        "reference/models.md",
        "reference/scrapers.md",
    ]
    for page in required_pages:
        assert (DOCS_DIR / page).exists(), f"docs/{page} not found"


def test_nav_pages_match_docs_directory():
    """All pages listed in zensical.toml nav must exist in docs/."""
    config = tomllib.loads(ZENSICAL_TOML.read_text())
    nav = config["project"].get("nav", [])

    def extract_paths(nav_items):
        paths = []
        for item in nav_items:
            for value in item.values():
                if isinstance(value, str):
                    if value:
                        paths.append(value)
                elif isinstance(value, list):
                    paths.extend(extract_paths(value))
        return paths

    for path in extract_paths(nav):
        assert (DOCS_DIR / path).exists(), f"Nav references docs/{path} but file not found"


def test_readme_is_not_empty():
    """README.md must contain substantive content."""
    readme = (PROJECT_ROOT / "README.md").read_text()
    assert len(readme) > 100, "README.md appears to be empty or trivially short"
    assert "Griddy Archive Manager" in readme, "README.md missing project name"


def test_readme_has_setup_instructions():
    """README.md must contain installation/setup instructions."""
    readme = (PROJECT_ROOT / "README.md").read_text()
    assert "uv sync" in readme, "README.md missing dependency install instructions"
    assert "migrate" in readme, "README.md missing migration instructions"


def test_readme_describes_both_domains():
    """README.md must cover both the Catalog and Holdings domains."""
    readme = (PROJECT_ROOT / "README.md").read_text()
    assert "Catalog" in readme, "README.md missing Catalog domain description"
    assert "Holdings" in readme, "README.md missing Holdings domain description"


def test_doc_dependencies_declared():
    """Doc dependencies must be declared in pyproject.toml."""
    config = tomllib.loads(PYPROJECT_PATH.read_text())
    groups = config.get("dependency-groups", {})
    assert "docs" in groups, "docs dependency group not found in pyproject.toml"
    docs_deps = groups["docs"]
    dep_names = [d.split(">")[0].split("[")[0].strip('"') for d in docs_deps]
    assert "zensical" in dep_names, "zensical not in docs dependencies"
    assert "mkdocstrings" in dep_names, "mkdocstrings not in docs dependencies"


def test_models_reference_page_has_key_models():
    """The models reference page must reference all key models."""
    content = (DOCS_DIR / "reference" / "models.md").read_text()
    required_models = [
        "League",
        "Season",
        "Game",
        "Team",
        "Venue",
        "Source",
        "Acquisition",
        "VideoAsset",
    ]
    for model in required_models:
        assert f"archive.models.{model}" in content, (
            f"Models reference missing {model}"
        )


def test_commands_page_documents_all_commands():
    """The commands page must document all management commands."""
    content = (DOCS_DIR / "commands.md").read_text()
    assert "scrape_games" in content, "commands.md missing scrape_games"
    assert "scrapegames" in content, "commands.md missing scrapegames"
    assert "scrapenflteams" in content, "commands.md missing scrapenflteams"
    assert "sandbox" in content, "commands.md missing sandbox"
