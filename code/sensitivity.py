#!/usr/bin/env python3
"""Sensitivity analysis of the architecture ranking (Online Resource 2).

For each factor an operator might doubt, this asks whether the lowest-carbon
architecture changes, and at which payload. Everything is computed from the
CSVs already shipped in the six data folders; no benchmark is re-run.

    1. operation mix      bulk retrievals and latest-frame reads per 2,000 inserts
    2. variability        each cell perturbed by its own run-to-run spread
    3. embodied carbon    retained storage, published factor range, 30-365 days
    4. grid and PUE       multiplicative, so the ranking cannot move
    5. scale              frame rate and camera count, linear
    6. host and corpus    the winners in each of the six data sets

Outputs go to ../sensitivity: one CSV per factor, LaTeX table fragments that
Online Resource 2 inputs directly, and two figures.

Usage:  python3 sensitivity.py [--out ../sensitivity] [--draws 20000]
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.colors import ListedColormap  # noqa: E402

from report_realcase import (  # noqa: E402  same loaders as the paper's figures
    FRAMES_PER_YEAR,
    PLOT_STYLE,
    ROOT,
    ROWS_PER_RUN,
    RUNS_PER_CELL,
    STYLE,
    emissions_kg,
    payload_mb,
    skipped_cells,
)

ENGINES = ["postgres", "postgres_minio", "mongodb"]
LABEL = {e: STYLE[e][2] for e in ENGINES}
OPS = ("insert", "retrieve", "point_read")
ORDER = ["360p", "480p", "720p", "1080p", "1440p", "4k", "5k", "6k"]
SHOW = {"4k": "4K", "5k": "5K", "6k": "6K"}

# (key, folder, label). The i9 ran the collage sweep; everything else ran on the i7.
DATASETS = [
    ("i9_collage", "data", "i9, collage"),
    ("i7_collage", "data_collage_i7", "i7, collage"),
    ("i7_networked", "data_frames_tapo", "i7, networked camera"),
    ("i7_builtin", "data_frames_webcam1", "i7, built-in camera"),
    ("i7_usb", "data_frames_webcam2", "i7, USB camera"),
    ("i7_fleet", "data_fleet", "i7, three cameras interleaved"),
]

# Factor 1: reads per 2,000 inserts (one insertion run). Equal weight is (1, 1).
BULK_PER_RUN = [0, 0.1, 0.25, 0.5, 1, 2, 5, 10]
POINT_PER_RUN = [0, 1, 10, 100, 1000, 2000]
MIXES = {"ingestion-only": (0.0, 0.0), "equal-weight": (1.0, 1.0)}

# Factor 3: embodied carbon of the storage medium, kg CO2eq per decimal GB of capacity.
# Both are the averages reported by Tannu and Nair (2023): 0.16 for SSDs (94 LCA reports,
# the value the paper uses) and 0.02 for HDDs (24 LCA reports). They are the only per-GB
# factors in the cited sources, so the range spans the choice of medium.
EMBODIED_KG_PER_GB = {"HDD": 0.02, "SSD": 0.16}
RETENTION_DAYS = [30, 90, 365]
SERVICE_LIFE_YEARS = 5  # SCI-style time share of a device's embodied carbon
FPS = 5

# Factor 4: the grids of the paper's Table 8 (g CO2eq/kWh); the data were logged at 676.
GRID_G_PER_KWH = [("Sweden", 41), ("France", 53), ("EU-27 average", 230), ("United States", 360),
                  ("China", 550), ("Indonesia", 676), ("India", 713)]
LOGGED_G_PER_KWH = 676
PUE_VALUES = [1.0, 1.5, 2.0]


@dataclass
class Dataset:
    key: str
    label: str
    profiles: list[str]
    payload: dict[str, float]
    carbon: dict[tuple[str, str, str], float]  # (engine, op, profile) -> mg per run
    cv: dict[tuple[str, str, str], float]      # (engine, op, profile) -> run-to-run CV
    amp: dict[tuple[str, str], float]          # (engine, profile) -> storage amplification
    missing: set[tuple[str, str]] = field(default_factory=set)

    def engines_at(self, profile: str) -> list[str]:
        return [e for e in ENGINES if (e, profile) not in self.missing]

    def mix(self, engine: str, profile: str, bulk: float, point: float) -> float:
        """mg per 2,000 stored frames under a mix of reads."""
        c = self.carbon
        return (c[(engine, "insert", profile)] + bulk * c[(engine, "retrieve", profile)]
                + point * c[(engine, "point_read", profile)])


def _last_row(path: Path) -> dict | None:
    if not path.exists():
        return None
    rows = list(csv.DictReader(path.open()))
    return rows[-1] if rows else None


def load(key: str, folder: str, label: str) -> Dataset:
    d = ROOT / folder
    kg = emissions_kg(d)
    skipped = skipped_cells(d)
    prefix = {"postgres": "results_postgres", "postgres_minio": "results_postgres_minio",
              "mongodb": "results_mongo"}
    profiles = [p for p in ORDER if any((e, "insert", p) in kg for e in ENGINES)]
    carbon, cv, amp, missing = {}, {}, {}, set()
    for p in profiles:
        for e in ENGINES:
            if (e, p) in skipped or any((e, op, p) not in kg for op in OPS):
                missing.add((e, p))
                continue
            for op in OPS:
                carbon[(e, op, p)] = kg[(e, op, p)] * 1e6 / RUNS_PER_CELL
                row = _last_row(d / f"{prefix[e]}_{op}_summary_{p}.csv") or {}
                mean_k, std_k = (("mean_duration_sec", "std_duration_sec") if op == "insert"
                                 else ("mean_latency_ms", "std_latency_ms"))
                mean, std = float(row.get(mean_k) or 0), float(row.get(std_k) or 0)
                cv[(e, op, p)] = std / mean if mean > 0 else 0.0
            ins = _last_row(d / f"{prefix[e]}_insert_summary_{p}.csv") or {}
            amp[(e, p)] = float(ins.get("mean_storage_amplification") or "nan")
    payload = {p: payload_mb(d, p) for p in profiles}
    profiles.sort(key=lambda p: payload[p])
    return Dataset(key, label, profiles, payload, carbon, cv, amp, missing)


def show(profile: str) -> str:
    return SHOW.get(profile, profile)


def winner(ds: Dataset, profile: str, bulk: float, point: float) -> str:
    return min(ds.engines_at(profile), key=lambda e: ds.mix(e, profile, bulk, point))


def write_csv(path: Path, header: list[str], rows: list[list]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


# --------------------------------------------------------------------------- #
# Factor 1: operation mix
# --------------------------------------------------------------------------- #
def factor_mix(sets: list[Dataset], out: Path) -> list[list]:
    rows = []
    for ds in sets:
        for p in ds.profiles:
            for bulk in BULK_PER_RUN:
                for point in POINT_PER_RUN:
                    w = winner(ds, p, bulk, point)
                    rows.append([ds.key, show(p), f"{ds.payload[p]:.3f}", bulk, point, LABEL[w]]
                                + [f"{ds.mix(e, p, bulk, point):.2f}" if e in ds.engines_at(p) else ""
                                   for e in ENGINES])
    write_csv(out / "factor1_operation_mix.csv",
              ["dataset", "profile", "payload_mb", "bulk_per_2000_inserts", "point_reads_per_2000_inserts",
               "greenest"] + [f"{LABEL[e]}_mg" for e in ENGINES], rows)
    return rows


def winners_along(ds: Dataset, bulk: float, point: float) -> str:
    """The sequence of greenest architectures by payload, run-length encoded."""
    seq = [(show(p), LABEL[winner(ds, p, bulk, point)]) for p in ds.profiles]
    runs: list[list] = []
    for prof, w in seq:
        if runs and runs[-1][0] == w:
            runs[-1][2] = prof
        else:
            runs.append([w, prof, prof])
    return "; ".join(f"{w} {a}" if a == b else f"{w} {a}--{b}" for w, a, b in runs)


def draw_mix(sets: list[Dataset], out: Path) -> None:
    order = {e: i for i, e in enumerate(ENGINES)}
    cmap = ListedColormap([STYLE[e][0] for e in ENGINES])
    chosen = [ds for ds in sets if ds.key in ("i9_collage", "i7_networked")]
    plt.rcParams.update(PLOT_STYLE)
    fig, axes = plt.subplots(2, len(chosen), figsize=(5.2 * len(chosen), 6.4), squeeze=False)
    for col, ds in enumerate(chosen):
        for row, (values, axis_label, fixed) in enumerate([
                (BULK_PER_RUN, "bulk retrievals per 2,000 inserts", "no latest-frame reads"),
                (POINT_PER_RUN, "latest-frame reads per 2,000 inserts", "no bulk retrievals")]):
            grid = np.array([[order[winner(ds, p, v, 0) if row == 0 else winner(ds, p, 0, v)]
                              for p in ds.profiles] for v in values])
            ax = axes[row][col]
            ax.imshow(grid, cmap=cmap, vmin=0, vmax=len(ENGINES) - 1, aspect="auto", origin="lower")
            ax.set_xticks(range(len(ds.profiles)))
            ax.set_xticklabels([f"{show(p)}\n{ds.payload[p]:.2f}" for p in ds.profiles], fontsize=8)
            ax.set_yticks(range(len(values)))
            ax.set_yticklabels([f"{v:g}" for v in values], fontsize=8)
            ax.set_ylabel(axis_label, fontsize=9)
            ax.set_title(f"{ds.label} ({fixed})", fontsize=10)
            if row == 1:
                ax.set_xlabel("resolution and payload (MB)", fontsize=9)
    handles = [plt.Rectangle((0, 0), 1, 1, color=STYLE[e][0]) for e in ENGINES]
    fig.legend(handles, [LABEL[e] for e in ENGINES], loc="lower center", ncol=3, frameon=False,
               bbox_to_anchor=(0.5, -0.02))
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    fig.savefig(out / "sensitivity_operation_mix.pdf")
    plt.close(fig)


# --------------------------------------------------------------------------- #
# Factor 2: measurement variability
# --------------------------------------------------------------------------- #
def factor_variability(sets: list[Dataset], out: Path, draws: int, seed: int = 20261106) -> list[list]:
    rng = np.random.default_rng(seed)
    rows = []
    for ds in sets:
        for p in ds.profiles:
            engines = ds.engines_at(p)
            for mix_name, (bulk, point) in MIXES.items():
                weights = {"insert": 1.0, "retrieve": bulk, "point_read": point}
                totals = np.zeros((draws, len(engines)))
                for j, e in enumerate(engines):
                    for op in OPS:
                        mean = ds.carbon[(e, op, p)] * weights[op]
                        if mean == 0:
                            continue
                        sample = rng.normal(mean, ds.cv[(e, op, p)] * mean, draws)
                        totals[:, j] += np.clip(sample, 0, None)
                nominal = winner(ds, p, bulk, point)
                wins = np.bincount(totals.argmin(axis=1), minlength=len(engines)) / draws
                share = {e: wins[j] for j, e in enumerate(engines)}
                rival = max((e for e in engines if e != nominal), key=lambda e: share[e])
                rows.append([ds.key, show(p), mix_name, LABEL[nominal], f"{share[nominal]:.3f}",
                             LABEL[rival], f"{share[rival]:.3f}",
                             "robust" if share[nominal] >= 0.95 else "within variability"])
    write_csv(out / "factor2_variability.csv",
              ["dataset", "profile", "mix", "greenest", "p_greenest", "closest_rival", "p_rival", "verdict"],
              rows)
    return rows


def max_cv(ds: Dataset) -> tuple[float, str]:
    key = max(ds.cv, key=ds.cv.get)
    return ds.cv[key], f"{LABEL[key[0]]} {key[1]} {show(key[2])}"


# --------------------------------------------------------------------------- #
# Factor 3: embodied carbon of retained storage
# --------------------------------------------------------------------------- #
AMP_BASES = {
    # MongoDB's sub-unity readings come from one collStats call straight after insertion,
    # with no checkpoint forced, and they recur on distinct real frames, so a second basis
    # assumes no architecture keeps less on disk than the payload itself.
    "measured": lambda a: a,
    "floor 1.0": lambda a: max(a, 1.0),
}


def factor_embodied(sets: list[Dataset], out: Path) -> list[list]:
    """Operational carbon per camera-year plus the embodied carbon of the retained volume.

    Embodied carbon is charged as an SCI-style time share: the capacity that holds the
    retention window is provisioned once, and its manufacturing carbon is spread over a
    SERVICE_LIFE_YEARS drive life. Also reports the retention period beyond which the
    operational winner loses to an architecture with a smaller on-disk footprint.
    """
    factors = {k: v for k, v in EMBODIED_KG_PER_GB.items() if v is not None}
    rows = []
    for ds in sets:
        for p in ds.profiles:
            engines = ds.engines_at(p)
            gb_per_day = ds.payload[p] * FPS * 86400 / 1000  # decimal GB of payload per camera-day
            for mix_name, (bulk, point) in MIXES.items():
                op_kg = {e: ds.mix(e, p, bulk, point) / ROWS_PER_RUN * FRAMES_PER_YEAR / 1e6 for e in engines}
                base = min(engines, key=op_kg.get)
                for basis, adjust in AMP_BASES.items():
                    amp = {e: adjust(ds.amp[(e, p)]) for e in engines}
                    for fname, f in factors.items():
                        rate = {e: gb_per_day * amp[e] * f / SERVICE_LIFE_YEARS for e in engines}  # kg/yr per day kept
                        # Footprints within 0.5% are a tie, not a smaller footprint.
                        breakeven = [(op_kg[c] - op_kg[base]) / (rate[base] - rate[c])
                                     for c in engines if c != base and rate[c] < rate[base] * 0.995]
                        be = min(breakeven) if breakeven else float("inf")
                        for days in RETENTION_DAYS:
                            tot = {e: op_kg[e] + rate[e] * days for e in engines}
                            w = min(engines, key=tot.get)
                            rows.append([ds.key, show(p), mix_name, basis, fname, f, days, LABEL[base], LABEL[w],
                                         "yes" if w != base else "no",
                                         f"{rate[base] * days / op_kg[base]:.1f}",
                                         "never" if be == float("inf") else f"{be:.1f}"]
                                        + [f"{op_kg[e]:.3f}" if e in engines else "" for e in ENGINES]
                                        + [f"{rate[e] * days:.2f}" if e in engines else "" for e in ENGINES])
    write_csv(out / "factor3_embodied.csv",
              ["dataset", "profile", "mix", "amplification", "factor", "kg_per_gb", "retention_days",
               "greenest_operational", "greenest_with_embodied", "changes", "embodied_over_operational",
               "breakeven_retention_days"]
              + [f"{LABEL[e]}_operational_kg_yr" for e in ENGINES]
              + [f"{LABEL[e]}_embodied_kg_yr" for e in ENGINES], rows)
    return rows


# --------------------------------------------------------------------------- #
# Factor 4: grid intensity and PUE
# --------------------------------------------------------------------------- #
def factor_grid(sets: list[Dataset], out: Path) -> list[list]:
    ds = next(s for s in sets if s.key == "i9_collage")
    common = [p for p in ds.profiles if not any((e, p) in ds.missing for e in ENGINES)]
    cumulative = {e: sum(ds.mix(e, p, 1, 1) for p in common) for e in ENGINES}  # mg, logged grid
    rows = []
    for region, g in GRID_G_PER_KWH:
        for pue in PUE_VALUES:
            vals = {e: cumulative[e] * g / LOGGED_G_PER_KWH * pue / 1000 for e in ENGINES}  # g CO2eq
            rows.append([region, g, pue] + [f"{vals[e]:.3f}" for e in ENGINES]
                        + [LABEL[min(vals, key=vals.get)]])
    write_csv(out / "factor4_grid_pue.csv",
              ["region", "g_per_kwh", "pue"] + [f"{LABEL[e]}_g" for e in ENGINES] + ["lowest"], rows)
    return rows


# --------------------------------------------------------------------------- #
# Factor 5: scale, i.e. the materiality sheet (linear in frame rate and cameras)
# --------------------------------------------------------------------------- #
MATERIALITY_CASES = [("i7_networked", "1080p", "deployment payload"), ("i9_collage", "4k", "4K collage payload")]
MATERIALITY_GRIDS = [("Indonesia", 676), ("EU-27 average", 230), ("Sweden", 41)]
SITE_SIZES = [1, 10, 100, 1000]


def factor_scale(sets: list[Dataset], out: Path) -> list[list]:
    """Annual ingestion carbon and savings per camera and per site, at PUE 1.0 and 1.5."""
    by_key = {ds.key: ds for ds in sets}
    rows = []
    for key, profile, label in MATERIALITY_CASES:
        ds = by_key[key]
        engines = ds.engines_at(profile)
        kg = {e: ds.mix(e, profile, 0, 0) / ROWS_PER_RUN * FRAMES_PER_YEAR / 1e6 for e in engines}  # logged grid
        ranked = sorted(engines, key=kg.get)
        best, runner, worst = ranked[0], ranked[1], ranked[-1]
        for region, g in MATERIALITY_GRIDS:
            for pue in (1.0, 1.5):
                scale = g / LOGGED_G_PER_KWH * pue
                for cams in SITE_SIZES:
                    rows.append([label, f"{ds.payload[profile]:.3f}", region, g, pue, cams, LABEL[best],
                                 f"{kg[best] * scale * cams:.2f}",
                                 LABEL[runner], f"{(kg[runner] - kg[best]) * scale * cams:.2f}",
                                 f"{1 - kg[best] / kg[runner]:.1%}",
                                 LABEL[worst], f"{(kg[worst] - kg[best]) * scale * cams:.2f}",
                                 f"{1 - kg[best] / kg[worst]:.1%}"])
    write_csv(out / "factor5_materiality.csv",
              ["case", "payload_mb", "grid", "g_per_kwh", "pue", "cameras", "greenest", "greenest_kg_yr",
               "runner_up", "saving_vs_runner_up_kg_yr", "saving_vs_runner_up_pct",
               "costliest", "saving_vs_costliest_kg_yr", "saving_vs_costliest_pct"], rows)
    return rows


# --------------------------------------------------------------------------- #
# Factor 6: host and corpus
# --------------------------------------------------------------------------- #
def factor_host_corpus(sets: list[Dataset], out: Path) -> list[list]:
    rows = []
    for ds in sets:
        for mix_name, (bulk, point) in MIXES.items():
            rows.append([ds.key, ds.label, mix_name, winners_along(ds, bulk, point)])
    write_csv(out / "factor6_host_corpus.csv", ["dataset", "label", "mix", "greenest_by_payload"], rows)
    return rows


def worst_case_ratios(sets: list[Dataset], out: Path) -> list[list]:
    """Largest ratio to the greenest, per architecture, under the equal-weight mix."""
    rows = []
    for ds in sets:
        worst = {e: (0.0, "") for e in ENGINES}
        for p in ds.profiles:
            vals = {e: ds.mix(e, p, 1, 1) for e in ds.engines_at(p)}
            best = min(vals.values())
            for e, v in vals.items():
                if v / best > worst[e][0]:
                    worst[e] = (v / best, show(p))
        rows.append([ds.key] + [f"{worst[e][0]:.2f} ({worst[e][1]})" for e in ENGINES])
    write_csv(out / "worst_case_ratio.csv", ["dataset"] + [LABEL[e] for e in ENGINES], rows)
    return rows


# --------------------------------------------------------------------------- #
# LaTeX fragments for Online Resource 2 (input directly, so no number is retyped)
# --------------------------------------------------------------------------- #
def _tex(text: str) -> str:
    return text.replace("--", "--").replace("%", "\\%").replace("_", "\\_")


def write_tables(sets: list[Dataset], out: Path, var_rows: list[list], emb_rows: list[list],
                 grid_rows: list[list], worst_rows: list[list], scale_rows: list[list]) -> None:
    label = {ds.key: ds.label for ds in sets}

    # S-mix: greenest by payload under four mixes
    lines = []
    for ds in sets:
        cells = [winners_along(ds, b, p) for b, p in ((0, 0), (1, 1), (10, 0), (0, 2000))]
        lines.append(f"{ds.label} & " + " & ".join(cells) + r" \\")
    (out / "tab_mix.tex").write_text("\n".join(lines) + "\n")

    # S-cv: largest run-to-run variability per data set
    lines = []
    for ds in sets:
        parts = []
        for op in ("insert", "retrieve"):
            k = max((k for k in ds.cv if k[1] == op), key=ds.cv.get)
            parts.append(f"{ds.cv[k] * 100:.0f}\\% ({LABEL[k[0]]}, {show(k[2])})")
        lines.append(f"{ds.label} & " + " & ".join(parts) + r" \\")
    (out / "tab_cv.tex").write_text("\n".join(lines) + "\n")

    # S-var: winners that do not survive the perturbation
    lines = [f"{label[r[0]]} & {r[1]} & {r[2]} & {r[3]} ({float(r[4]):.2f}) & {r[5]} ({float(r[6]):.2f}) \\\\"
             for r in var_rows if r[-1] != "robust"]
    (out / "tab_variability.tex").write_text("\n".join(lines) + "\n")

    # S-embodied: ratio to operational, and where the winner changes within a year
    lines = []
    for ds in sets:
        for medium in EMBODIED_KG_PER_GB:
            sel = [r for r in emb_rows if r[0] == ds.key and r[4] == medium and r[2] == "ingestion-only"]
            ratios = [float(r[10]) for r in sel if r[3] == "floor 1.0" and r[6] == 30]
            cells = []
            for basis in AMP_BASES:
                seen = {}
                for r in sel:
                    if r[3] == basis and r[11] != "never" and float(r[11]) <= 365:
                        seen[r[1]] = (float(r[11]), r[8] if r[8] != r[7] else None)
                flips = []
                for prof, (days, _) in seen.items():
                    rival = next(r[8] for r in sel if r[3] == basis and r[1] == prof and r[6] == 365)
                    flips.append(f"{prof} to {rival} after {days:.0f}~d" if days >= 1 else f"{prof} to {rival} at once")
                cells.append("; ".join(flips) if flips else "no")
            lines.append(f"{ds.label} & {medium} & {min(ratios):.0f}--{max(ratios):.0f} & " + " & ".join(cells) + r" \\")
    (out / "tab_embodied.tex").write_text("\n".join(lines) + "\n")

    # S-grid: the paper's former Table 8, cumulative 360p--5K at PUE 1.0
    lines = []
    for r in grid_rows:
        if r[2] != 1.0:
            continue
        vals = [float(v) for v in r[3:6]]
        best = min(vals)
        cells = [f"\\textbf{{{v:.2f}}}" if v == best else f"{v:.2f}" for v in vals]
        lines.append(f"{r[0]} & {r[1]} & " + " & ".join(cells) + r" \\")
    (out / "tab_grid.tex").write_text("\n".join(lines) + "\n")

    # S-worst: worst case relative to the greenest, equal weight
    lines = [f"{label[r[0]]} & " + " & ".join(c.replace("(", "(").replace("x", "") for c in r[1:]) + r" \\"
             for r in worst_rows]
    (out / "tab_worst.tex").write_text("\n".join(lines) + "\n")

    # S-materiality: per camera and per 100 cameras, PUE 1.0
    lines = []
    for r in scale_rows:
        if r[4] != 1.0 or r[5] != 1:
            continue
        hundred = next(x for x in scale_rows if x[:5] == r[:5] and x[5] == 100)
        lines.append(f"{r[0]} & {r[2]} & {r[6]} {float(r[7]):.2f} & "
                     f"{r[8]}: {float(r[9]):.2f} ({_tex(r[10])}) & {r[11]}: {float(r[12]):.2f} ({_tex(r[13])}) & "
                     f"{float(hundred[9]):.0f} / {float(hundred[12]):.0f} \\\\")
    (out / "tab_materiality.tex").write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=ROOT / "sensitivity")
    parser.add_argument("--draws", type=int, default=20000)
    args = parser.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    sets = [load(*spec) for spec in DATASETS]
    for ds in sets:
        cv, where = max_cv(ds)
        print(f"{ds.label:32s} profiles {', '.join(show(p) for p in ds.profiles):45s} "
              f"max CV {cv:.1%} ({where})")

    factor_mix(sets, args.out)
    draw_mix(sets, args.out)
    print("\nFactor 1, greenest by payload:")
    for ds in sets:
        print(f"  {ds.label}")
        for bulk in BULK_PER_RUN:
            print(f"    bulk {bulk:<5g} point 0   : {winners_along(ds, bulk, 0)}")
        for point in POINT_PER_RUN[1:]:
            print(f"    bulk 0     point {point:<4g}: {winners_along(ds, 0, point)}")

    print("\nFactor 2, winners within run-to-run variability:")
    for row in factor_variability(sets, args.out, args.draws):
        if row[-1] != "robust":
            print("  ", row)

    emb = factor_embodied(sets, args.out)
    print("\nFactor 3 (SSD factor), embodied/operational at 30 days and break-even retention:")
    for r in emb:
        if r[4] == "SSD" and r[6] == 30:
            print(f"  {r[0]:13s} {r[1]:6s} {r[2]:15s} {r[3]:10s} op-winner {r[7]:8s} "
                  f"embodied/op {r[10]:>7s}  break-even {r[11]:>6s} d  with-embodied@30d {r[8]}")

    print("\nFactor 4, lowest cumulative 360p-5K footprint by grid and PUE:",
          sorted({r[-1] for r in factor_grid(sets, args.out)}))
    print("\nWorst case relative to the greenest (equal weight):")
    for row in worst_case_ratios(sets, args.out):
        print("  ", row)
    factor_host_corpus(sets, args.out)
    scale_rows = factor_scale(sets, args.out)
    write_tables(sets, args.out, factor_variability(sets, args.out, args.draws), emb,
                 factor_grid(sets, args.out), worst_case_ratios(sets, args.out), scale_rows)
    print(f"\nWrote CSVs, LaTeX fragments and figures to {args.out}")


if __name__ == "__main__":
    main()
