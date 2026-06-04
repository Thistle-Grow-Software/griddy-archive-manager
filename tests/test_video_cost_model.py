"""Tests for the ADR-0008 video cost projection (TGF-363, AC4).

The script lives under ``scripts/`` (not an importable package), so it is loaded
by path. The tests pin the arithmetic and, most importantly, the acceptance
criterion: the projection must land the approach in the ~$10s/mo class, not
~$1000s/mo, across realistic viewing volumes.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).resolve().parent.parent / "scripts" / "video_cost_model.py"


@pytest.fixture(scope="module")
def cm():
    spec = importlib.util.spec_from_file_location("video_cost_model", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    # Register before exec so @dataclass can resolve annotations against the module.
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_objects_per_stream_uses_measured_segment_count(cm):
    # manifest + init + media segments
    assert cm.objects_per_stream(180, 6, segment_count=300) == 302


def test_objects_per_stream_estimates_from_duration_when_unmeasured(cm):
    # 180 min / 6s = 1800 media segments, + manifest + init.
    assert cm.objects_per_stream(180, 6, segment_count=None) == 1802


def test_measurements_anchor_the_model(cm):
    measured = cm.build_catalog_model(
        {
            "size_ratio": 1.0,
            "segment_count": 250,
            "segment_duration_seconds": 6,
            "duration_seconds": 2400,
        }
    )
    assert measured.objects_per_stream == 252
    # Packaged size billed in decimal GB, derived from the catalog TiB.
    assert measured.packaged_gb > 3000  # 2.95 TiB ~ 3243 GB


def test_storage_uses_decimal_gb_and_published_rate(cm):
    model = cm.build_catalog_model(None)
    scenario = cm.UsageScenario("t", streams_per_month=0)
    cost = cm.project_cost(model, scenario)
    expected_storage = model.packaged_gb * cm.R2_STORAGE_PER_GB_MONTH
    assert cost.storage == pytest.approx(expected_storage)
    # No viewing → reads cost nothing; only the $5 Workers base + storage.
    assert cost.class_b == pytest.approx(0.0)
    assert cost.workers == pytest.approx(cm.WORKERS_PLAN_BASE_MONTHLY)


def test_egress_is_free(cm):
    assert cm.R2_EGRESS_PER_GB == 0.0


def test_scrub_overhead_increases_read_cost(cm):
    model = cm.build_catalog_model(None)
    no_scrub = cm.project_cost(model, cm.UsageScenario("a", 10_000, scrub_overhead=0.0))
    scrub = cm.project_cost(model, cm.UsageScenario("b", 10_000, scrub_overhead=0.5))
    assert scrub.class_b > no_scrub.class_b


def test_acceptance_criterion_tens_not_thousands(cm):
    """The whole point of AC4: distinguish ~$10/mo from ~$1000/mo."""
    model = cm.build_catalog_model(None)
    for scenario in cm.DEFAULT_SCENARIOS:
        total = cm.project_cost(model, scenario).total
        assert total < 1000, (
            f"{scenario.name} projected ${total:,.2f}, expected < $1000"
        )
    # Even the heaviest scenario should be well under $1000; the lightest tens.
    light = cm.project_cost(model, cm.DEFAULT_SCENARIOS[0]).total
    assert light < 100


def test_report_renders_markdown_table(cm):
    model = cm.build_catalog_model(None)
    report = cm.render_report(model)
    assert "Projected monthly cost by viewing volume" in report
    assert "Total/mo" in report
    assert report.count("|") > 10  # a real table, not an empty stub
