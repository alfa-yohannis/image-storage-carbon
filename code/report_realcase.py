#!/usr/bin/env python3
"""Regenerate the four figures introduced by the revision.

report.py draws the six figures of the original controlled sweep. This module
draws the four that the revision added, all of which compare two corpora or two
hosts and therefore need more than one data directory at a time:

    realframes_carbon.pdf   collage beside real camera frames, same host
    crossover_collage.pdf   where the ingestion crossover falls under the collage
    crossover_realcase.pdf  where it falls for the deployment's own payloads
    applied_annual.pdf      the framework applied to one camera for a year

Everything is derived from the CSVs shipped with the artifact, so the figures in
the paper can be reproduced without re-running the benchmark. Colours, markers,
and font sizes deliberately match report.py so the ten figures read as one set.

Usage:  python3 report_realcase.py [--out ../figures]
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# Same palette and markers as report.py, so all ten figures match.
STYLE = {
    "postgres": ("#1f77b4", "o", "Postgre"),
    "postgres_minio": ("#2ca02c", "s", "PostMin"),
    "mongodb": ("#d62728", "^", "Mongo"),
}
ENGINES = list(STYLE)

# One tracker covers n_runs repetitions of rows_per_run inserts.
RUNS_PER_CELL = 5
ROWS_PER_RUN = 2000

# The deployment captures continuously at 5 frames per second.
FRAMES_PER_YEAR = 5 * 365 * 24 * 3600

PLOT_STYLE = {
    "font.size": 11,
    "axes.labelsize": 12,
    "legend.fontsize": 9.5,
    "xtick.labelsize": 10,
    "ytick.labelsize": 10,
    "savefig.bbox": "tight",
    "axes.axisbelow": True,
    "figure.dpi": 120,
}


def emissions_kg(data_dir: Path) -> dict[tuple[str, str, str], float]:
    """Read CodeCarbon's log into {(engine, operation, profile): kg CO2eq}."""
    table: dict[tuple[str, str, str], float] = {}
    path = data_dir / "emissions.csv"
    if not path.exists():
        return table
    for row in csv.DictReader(path.open()):
        name = row["project_name"]
        for operation in ("insert", "retrieve", "point_read"):
            marker = f"_{operation}_"
            if marker in name:
                engine, profile = name.split(marker)
                table[(engine, operation, profile)] = float(row["emissions"])
                break
    return table


def skipped_cells(data_dir: Path) -> set[tuple[str, str]]:
    """Cells the harness attempted and could not complete.

    A failed cell still leaves a partial tracker in emissions.csv, covering
    however much work happened before the error. Plotting that would show
    MongoDB's 6K point as merely cheap when it is in fact infeasible, so every
    reader of the emissions log must exclude these first.
    """
    path = data_dir / "skipped.csv"
    if not path.exists():
        return set()
    return {(row["engine"], row["profile"]) for row in csv.DictReader(path.open())}


def ingestion_mg_per_frame(data_dir: Path, engine: str, profile: str) -> float | None:
    """Amortised ingestion carbon for one stored frame, in mg CO2eq."""
    if (engine, profile) in skipped_cells(data_dir):
        return None
    kg = emissions_kg(data_dir).get((engine, "insert", profile))
    if kg is None:
        return None
    return kg * 1e6 / (RUNS_PER_CELL * ROWS_PER_RUN)


def total_mg_per_run(data_dir: Path, engine: str, profile: str) -> float | None:
    """One insertion, one bulk retrieval, and one latest-frame read, in mg CO2eq."""
    if (engine, profile) in skipped_cells(data_dir):
        return None
    table = emissions_kg(data_dir)
    parts = [table.get((engine, op, profile)) for op in ("insert", "retrieve", "point_read")]
    if any(p is None for p in parts):
        return None
    return sum(parts) * 1e6 / RUNS_PER_CELL


def payload_mb(data_dir: Path, profile: str) -> float | None:
    """Size of the payload actually stored at this profile, from any engine's summary."""
    for stem in ("results_postgres", "results_mongo", "results_postgres_minio"):
        path = data_dir / f"{stem}_insert_summary_{profile}.csv"
        if not path.exists():
            continue
        rows = list(csv.DictReader(path.open()))
        if rows and rows[-1].get("payload_size_mb"):
            return float(rows[-1]["payload_size_mb"])
    return None


def draw_realframes(out_dir: Path) -> None:
    """Carbon per run against resolution: identical rows beside distinct real frames.

    Both panels come from the same host, so the only thing that changes between
    them is how the payload was built. That is the whole point of the figure.
    """
    profiles = ["360p", "480p", "720p", "1080p"]
    panels = [
        (ROOT / "data_collage_i7", "(a) Deterministic collage (identical rows)"),
        (ROOT / "data_frames_tapo", "(b) Real camera frames (distinct rows)"),
    ]

    fig, axes = plt.subplots(1, 2, figsize=(9.02, 3.49), sharey=True)
    for ax, (data_dir, title) in zip(axes, panels):
        for engine in ENGINES:
            colour, marker, label = STYLE[engine]
            ys = [total_mg_per_run(data_dir, engine, p) for p in profiles]
            xs = [i for i, y in enumerate(ys) if y is not None]
            ax.plot(xs, [ys[i] for i in xs], marker=marker, color=colour,
                    label=label, linewidth=1.6, markersize=6)
        ax.set_yscale("log")
        ax.set_xticks(range(len(profiles)))
        ax.set_xticklabels(profiles)
        ax.set_xlabel("Resolution")
        ax.set_title(title, fontsize=10.5)
        ax.grid(True, which="both", alpha=0.25)
    axes[0].set_ylabel("Amortised carbon per run (mg CO$_2$eq)")
    axes[0].legend(frameon=False)
    fig.tight_layout()
    fig.savefig(out_dir / "realframes_carbon.pdf")
    plt.close(fig)


def draw_crossover(out_dir: Path, data_dir: Path, profiles: list[str], filename: str,
                   log: bool, bracket_label: str, resolution_axis: bool) -> None:
    """Ingestion carbon against measured payload size, with the crossover bracket.

    The bracket is drawn between the two adjacent measurements that straddle the
    change of winner. No interpolation is implied: we know the ordering flips
    somewhere in that interval, and nothing finer than that.
    """
    sizes = {p: payload_mb(data_dir, p) for p in profiles}
    series: dict[str, list[tuple[float, float]]] = {}
    for engine in ENGINES:
        points = []
        for profile in profiles:
            size = sizes[profile]
            carbon = ingestion_mg_per_frame(data_dir, engine, profile)
            if size is not None and carbon is not None:
                points.append((size, carbon))
        series[engine] = sorted(points)

    # Find where the lowest-carbon engine changes, walking up the payload axis.
    ordered = [p for p in profiles if sizes[p] is not None]
    ordered.sort(key=lambda p: sizes[p])
    lowest = []
    for profile in ordered:
        candidates = {e: ingestion_mg_per_frame(data_dir, e, profile) for e in ENGINES}
        candidates = {e: v for e, v in candidates.items() if v is not None}
        lowest.append((sizes[profile], min(candidates, key=candidates.get) if candidates else None))
    bracket = None
    for (x0, w0), (x1, w1) in zip(lowest, lowest[1:]):
        if w0 and w1 and w0 != w1:
            bracket = (x0, x1)
            break

    fig, ax = plt.subplots(figsize=(5.78, 3.97) if log else (5.77, 4.02))
    if bracket:
        ax.axvspan(bracket[0], bracket[1], color="#999999", alpha=0.18, zorder=0)
        mid = (bracket[0] * bracket[1]) ** 0.5 if log else sum(bracket) / 2
        ax.annotate(bracket_label, xy=(mid, 0.06), xycoords=("data", "axes fraction"),
                    ha="center", fontsize=8.5, style="italic", color="#444444")
    for engine in ENGINES:
        colour, marker, label = STYLE[engine]
        points = series[engine]
        if not points:
            continue
        ax.plot([p[0] for p in points], [p[1] for p in points], marker=marker,
                color=colour, label=label, linewidth=1.6, markersize=6)
    if log:
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("Payload size (MB, log scale)")
    else:
        ax.set_xlabel("Measured payload size (MB)")
    ax.set_ylabel("Ingestion carbon (mg CO$_2$eq per frame)")
    ax.grid(True, which="both", alpha=0.25)
    ax.legend(frameon=False, loc="upper left")

    if resolution_axis:
        # This camera's resolutions, on the payload axis where they actually fall.
        top = ax.secondary_xaxis("top")
        ticks = [sizes[p] for p in ordered]
        labels = [p if p != "1080p" else "1080p\n(deployment)" for p in ordered]
        top.set_xticks(ticks)
        top.set_xticklabels(labels, fontsize=8.5)
        top.set_xlabel("Resolution of this camera", fontsize=10)

    fig.tight_layout()
    fig.savefig(out_dir / filename)
    plt.close(fig)


def draw_applied(out_dir: Path) -> None:
    """Annual carbon for one camera, under ingestion-only and equal-weight profiles.

    The two groups of bars select different architectures, which is the point:
    the operation profile is part of the decision, not a detail of presentation.
    """
    data_dir = ROOT / "data_frames_tapo"
    order = ["postgres", "postgres_minio", "mongodb"]
    write, total = [], []
    for engine in order:
        per_frame = ingestion_mg_per_frame(data_dir, engine, "1080p") or 0.0
        run_total = total_mg_per_run(data_dir, engine, "1080p") or 0.0
        write.append(per_frame * FRAMES_PER_YEAR / 1e6)
        total.append(run_total / ROWS_PER_RUN * FRAMES_PER_YEAR / 1e6)

    xs = range(len(order))
    width = 0.38
    fig, ax = plt.subplots(figsize=(5.28, 3.70))
    bars = [
        ax.bar([x - width / 2 for x in xs], write, width,
               color=[STYLE[e][0] for e in order], label="ingestion only"),
        ax.bar([x + width / 2 for x in xs], total, width, alpha=0.45, hatch="//",
               color=[STYLE[e][0] for e in order], label="ingestion + reads"),
    ]
    for group in bars:
        ax.bar_label(group, fmt="%.2f", fontsize=8.5, padding=2)
    ax.set_xticks(list(xs))
    ax.set_xticklabels([STYLE[e][2] for e in order])
    ax.set_ylabel("kg CO$_2$eq per camera per year")
    ax.set_ylim(0, max(total + write) * 1.18)
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(frameon=False, loc="upper left")
    fig.tight_layout()
    fig.savefig(out_dir / "applied_annual.pdf")
    plt.close(fig)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default=str(ROOT / "figures"),
                        help="directory to write the PDFs into")
    args = parser.parse_args()
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    plt.rcParams.update(PLOT_STYLE)

    draw_realframes(out_dir)
    draw_crossover(out_dir, ROOT / "data", ["360p", "480p", "720p", "1080p", "1440p", "4k", "5k", "6k"],
                   "crossover_collage.pdf", log=True,
                   bracket_label="crossover bracket\n1.40–2.99 MB", resolution_axis=False)
    draw_crossover(out_dir, ROOT / "data_frames_tapo", ["360p", "480p", "720p", "1080p"],
                   "crossover_realcase.pdf", log=False,
                   bracket_label="crossover bracket\n0.09–0.15 MB", resolution_axis=True)
    draw_applied(out_dir)

    print(f"[report] wrote 4 revision figures to {out_dir}")


if __name__ == "__main__":
    main()
