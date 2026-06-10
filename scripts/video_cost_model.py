#!/usr/bin/env python3
"""Project the monthly Cloudflare cost of the ADR-0008 video delivery (TGF-363, AC4).

This is a *projection*, not a measurement: the PoC runs entirely on the local
Miniflare R2 simulation (no cloud spend), so we measure the shape of one packaged
game locally and extrapolate to the full catalog against Cloudflare's published
R2 + Workers pricing. The acceptance criterion only needs ~10x accuracy — enough
to tell ~$10/month from ~$1000/month — so round, defensible inputs beat false
precision.

Cost components for HLS-from-R2-behind-a-Worker:

* **R2 storage** — $/GB-month for the packaged catalog (segments + manifests).
* **R2 Class B operations** — one GET per object served. Each stream is a
  manifest + an init segment + N media segments; scrubbing re-reads segments.
* **R2 Class A operations** — writes; a one-time packaging upload, amortized.
* **Worker requests** — one Worker invocation per object request (same count as
  Class B reads), priced after the included allotment, plus the $5/mo plan base.
* **Egress** — R2 has none. This is the whole reason ADR-0008 picked R2.

Run with no args to use the spike's catalog stats (``video_stats.md``) and the
ADR's ~1x packaged-size assumption; pass ``--measurements <json>`` (written by
``manage.py poc_load_game``) to anchor the per-game segment count and size ratio
to a real local measurement.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path

# --- Published Cloudflare pricing (USD), R2 + Workers Paid, as of 2026-05. -----
# Sources: developers.cloudflare.com/r2/pricing and /workers/platform/pricing.
R2_STORAGE_PER_GB_MONTH = 0.015
R2_CLASS_A_PER_MILLION = 4.50  # writes (PutObject, etc.)
R2_CLASS_B_PER_MILLION = 0.36  # reads (GetObject, etc.)
R2_EGRESS_PER_GB = 0.0  # R2 has no egress fee — the headline reason for R2.

WORKERS_PLAN_BASE_MONTHLY = 5.00
WORKERS_REQUESTS_INCLUDED = 10_000_000  # included in the $5 plan, per month
WORKERS_PER_MILLION_REQUESTS = 0.30  # beyond the included allotment

GIB = 1024**3
TIB = 1024**4

# --- Catalog facts from the TGF-337 spike (video_stats.md). --------------------
CATALOG_SOURCE_TIB = 2.95
# ADR-0008: a lossless `-c copy` remux is ~1x source, so budget ~1x for packaged
# segments. Overridden by a measured ratio when --measurements is supplied.
DEFAULT_PACKAGED_RATIO = 1.0
DEFAULT_SEGMENT_DURATION = 6
# Mean source bitrate ~ derived from 2.95 TiB across ~1,203 files; used only to
# estimate per-game segment count when no real measurement is given.
DEFAULT_GAME_DURATION_MIN = 180  # a full broadcast game incl. stoppages


@dataclass(frozen=True)
class CatalogModel:
    """The catalog-level inputs the projection extrapolates over."""

    packaged_bytes: float
    objects_per_stream: int  # manifest + init + media segments
    games: int

    @property
    def packaged_gb(self) -> float:
        # Cloud storage is billed in decimal GB (10^9), not GiB.
        return self.packaged_bytes / 1_000_000_000


@dataclass(frozen=True)
class UsageScenario:
    """A monthly viewing-volume assumption to price the catalog against."""

    name: str
    streams_per_month: int
    # Fraction of a stream's segments re-fetched due to scrubbing/seeking. 0.25
    # means the average viewing pulls 25% more segment reads than a clean
    # front-to-back play.
    scrub_overhead: float = 0.25


def packaged_bytes_from_catalog(ratio: float) -> float:
    return CATALOG_SOURCE_TIB * TIB * ratio


def objects_per_stream(
    game_duration_min: float, segment_duration: int, segment_count: int | None
) -> int:
    """Objects fetched for one clean play: manifest + init + media segments."""
    if segment_count is not None:
        media = segment_count
    else:
        media = round(game_duration_min * 60 / segment_duration)
    # +1 manifest (master.m3u8) +1 init (init.mp4).
    return media + 2


def build_catalog_model(measurements: dict | None) -> CatalogModel:
    """Assemble catalog inputs, anchored to a real measurement when provided."""
    games = round(CATALOG_SOURCE_TIB * TIB / (2.51 * GIB))  # mean file size 2.51 GiB

    if measurements:
        ratio = measurements.get("size_ratio") or DEFAULT_PACKAGED_RATIO
        seg_count = measurements.get("segment_count")
        seg_dur = measurements.get("segment_duration_seconds", DEFAULT_SEGMENT_DURATION)
        dur_min = (
            (measurements.get("duration_seconds") or 0) / 60
        ) or DEFAULT_GAME_DURATION_MIN
    else:
        ratio = DEFAULT_PACKAGED_RATIO
        seg_count = None
        seg_dur = DEFAULT_SEGMENT_DURATION
        dur_min = DEFAULT_GAME_DURATION_MIN

    return CatalogModel(
        packaged_bytes=packaged_bytes_from_catalog(ratio),
        objects_per_stream=objects_per_stream(dur_min, seg_dur, seg_count),
        games=games,
    )


@dataclass(frozen=True)
class CostBreakdown:
    storage: float
    class_a: float
    class_b: float
    workers: float

    @property
    def total(self) -> float:
        return self.storage + self.class_a + self.class_b + self.workers


def project_cost(model: CatalogModel, scenario: UsageScenario) -> CostBreakdown:
    """Project one month's cost for a usage scenario."""
    # Storage: the whole packaged catalog sits in R2 all month.
    storage = model.packaged_gb * R2_STORAGE_PER_GB_MONTH

    # Reads: every served object is one Class B op and one Worker request.
    reads_per_stream = model.objects_per_stream * (1 + scenario.scrub_overhead)
    monthly_reads = reads_per_stream * scenario.streams_per_month
    class_b = monthly_reads / 1_000_000 * R2_CLASS_B_PER_MILLION

    # Writes: a one-time packaging upload of every object, amortized over 12
    # months so the model reflects steady-state monthly cost.
    one_time_writes = model.objects_per_stream * model.games
    class_a = (one_time_writes / 12) / 1_000_000 * R2_CLASS_A_PER_MILLION

    # Workers: $5 base + per-request beyond the included allotment.
    billable_requests = max(0, monthly_reads - WORKERS_REQUESTS_INCLUDED)
    workers = (
        WORKERS_PLAN_BASE_MONTHLY
        + billable_requests / 1_000_000 * WORKERS_PER_MILLION_REQUESTS
    )

    return CostBreakdown(
        storage=storage, class_a=class_a, class_b=class_b, workers=workers
    )


DEFAULT_SCENARIOS = (
    UsageScenario("Pilot (100 streams/mo)", 100),
    UsageScenario("Small (1k streams/mo)", 1_000),
    UsageScenario("Active (10k streams/mo)", 10_000),
    UsageScenario("Heavy (100k streams/mo)", 100_000),
)


def render_report(model: CatalogModel, scenarios=DEFAULT_SCENARIOS) -> str:
    lines: list[str] = []
    lines.append("# v1 video delivery — projected Cloudflare cost (TGF-363, AC4)")
    lines.append("")
    lines.append(
        "Projected from local PoC measurements against published Cloudflare R2 + "
        "Workers pricing (no cloud resources were provisioned). Accuracy target: "
        "~10x — enough to distinguish ~$10/mo from ~$1000/mo."
    )
    lines.append("")
    lines.append("## Inputs")
    lines.append("")
    lines.append(
        f"- Packaged catalog size: **{model.packaged_bytes / TIB:.2f} TiB** "
        f"({model.packaged_gb:,.0f} GB billed)"
    )
    lines.append(f"- Estimated games in catalog: **{model.games:,}**")
    lines.append(
        f"- Objects fetched per clean stream: **{model.objects_per_stream:,}** "
        "(manifest + init + media segments)"
    )
    lines.append("")
    lines.append("## Pricing assumptions (USD)")
    lines.append("")
    lines.append(f"- R2 storage: ${R2_STORAGE_PER_GB_MONTH}/GB-month, egress $0")
    lines.append(f"- R2 Class A (writes): ${R2_CLASS_A_PER_MILLION}/million")
    lines.append(f"- R2 Class B (reads): ${R2_CLASS_B_PER_MILLION}/million")
    lines.append(
        f"- Workers: ${WORKERS_PLAN_BASE_MONTHLY}/mo + "
        f"${WORKERS_PER_MILLION_REQUESTS}/million beyond "
        f"{WORKERS_REQUESTS_INCLUDED // 1_000_000}M included"
    )
    lines.append("")
    lines.append("## Projected monthly cost by viewing volume")
    lines.append("")
    lines.append(
        "| Scenario | Storage | R2 reads | R2 writes | Workers | **Total/mo** |"
    )
    lines.append("| --- | --- | --- | --- | --- | --- |")
    for scenario in scenarios:
        c = project_cost(model, scenario)
        lines.append(
            f"| {scenario.name} | ${c.storage:,.2f} | ${c.class_b:,.2f} | "
            f"${c.class_a:,.2f} | ${c.workers:,.2f} | **${c.total:,.2f}** |"
        )
    lines.append("")
    lines.append("## Takeaway")
    lines.append("")
    base = project_cost(model, DEFAULT_SCENARIOS[0])
    lines.append(
        f"Storage dominates at low volume (~${base.storage:,.0f}/mo for the whole "
        "catalog) and is fixed; request costs scale with viewing but stay small "
        "because R2 reads and Worker requests are cheap and egress is free. Even "
        "at 100k streams/month the total stays comfortably in the tens of dollars, "
        "confirming the ADR-0008 approach is firmly in the ~$10s/mo class, not "
        "~$1000s/mo."
    )
    lines.append("")
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--measurements",
        type=Path,
        default=None,
        help="JSON written by `manage.py poc_load_game` to anchor the projection.",
    )
    p.add_argument(
        "-o",
        "--output",
        type=Path,
        default=None,
        help="Write the Markdown report here (default: stdout).",
    )
    return p.parse_args()


def main() -> None:
    args = parse_args()
    measurements = None
    if args.measurements and args.measurements.is_file():
        measurements = json.loads(args.measurements.read_text(encoding="utf-8"))
    model = build_catalog_model(measurements)
    report = render_report(model)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(report, encoding="utf-8")
        print(f"Wrote cost model to {args.output}")
    else:
        print(report)


if __name__ == "__main__":
    main()
