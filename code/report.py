#!/usr/bin/env python3
"""Three-way reporter: aggregates the per-engine summary CSVs in data/ into one
combined table and (if matplotlib is available) writes comparison figures to
figures/. Carbon is read directly from data/emissions.csv.

Usage: python report.py
"""
from __future__ import annotations

import csv
from pathlib import Path

from config import DEFAULT_SWEEP, Locations

ENGINES = [
    ("postgres", "PostgreSQL", "results_postgres"),
    ("postgres_minio", "PostgreSQL+MinIO", "results_postgres_minio"),
    ("mongodb", "MongoDB", "results_mongo"),
]
DIMENSIONS = ("insert", "retrieve", "point_read")


def _read_last(path: Path) -> dict | None:
    if not path.exists():
        return None
    with path.open(newline="") as handle:
        rows = list(csv.DictReader(handle))
    return rows[-1] if rows else None


class Reporter:
    def __init__(self, locations: Locations):
        self.loc = locations
        self.data_dir = locations.data_dir
        self.figures_dir = locations.figures_dir

    # ---- carbon (kg -> mg) per <engine>_<dimension>_<profile> ----------- #
    def _emissions(self) -> dict[str, float]:
        path = self.data_dir / "emissions.csv"
        out: dict[str, float] = {}
        if not path.exists():
            return out
        with path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                name = row.get("project_name", "")
                try:
                    out[name] = float(row.get("emissions", 0.0)) * 1_000_000.0  # kg -> mg
                except (TypeError, ValueError):
                    continue
        return out

    # ---- cells skipped after repeated failures -------------------------- #
    def _skipped(self) -> set[tuple[str, str]]:
        path = self.data_dir / "skipped.csv"
        out: set[tuple[str, str]] = set()
        if not path.exists():
            return out
        with path.open(newline="") as handle:
            for row in csv.DictReader(handle):
                out.add((row.get("engine", ""), row.get("profile", "")))
        return out

    def build(self) -> Path:
        emissions = self._emissions()
        skipped = self._skipped()
        combined = self.data_dir / "threeway_summary.csv"
        fields = ["profile"]
        for key, _, _ in ENGINES:
            fields += [f"{key}_insert_rows_per_sec", f"{key}_storage_amp",
                       f"{key}_retrieve_ms", f"{key}_point_read_ms", f"{key}_carbon_mg"]

        with combined.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields)
            writer.writeheader()
            for profile in DEFAULT_SWEEP:
                row = {"profile": profile}
                for key, _, prefix in ENGINES:
                    if (key, profile) in skipped:
                        for suffix in ("insert_rows_per_sec", "storage_amp", "retrieve_ms",
                                       "point_read_ms", "carbon_mg"):
                            row[f"{key}_{suffix}"] = ""
                        continue
                    ins = _read_last(self.data_dir / f"{prefix}_insert_summary_{profile}.csv")
                    ret = _read_last(self.data_dir / f"{prefix}_retrieve_summary_{profile}.csv")
                    prd = _read_last(self.data_dir / f"{prefix}_point_read_summary_{profile}.csv")
                    row[f"{key}_insert_rows_per_sec"] = (ins or {}).get("mean_rows_per_sec", "")
                    row[f"{key}_storage_amp"] = (ins or {}).get("mean_storage_amplification", "")
                    row[f"{key}_retrieve_ms"] = (ret or {}).get("mean_latency_ms", "")
                    row[f"{key}_point_read_ms"] = (prd or {}).get("mean_latency_ms", "")
                    carbon = sum(emissions.get(f"{key}_{dim}_{profile}", 0.0) for dim in DIMENSIONS)
                    row[f"{key}_carbon_mg"] = round(carbon, 3) if carbon else ""
                writer.writerow(row)
        print(f"[report] wrote {combined}")

        self._figures(combined)
        return combined

    # Per-engine display style and CSV prefix (key -> colour, marker, label, prefix).
    _STYLE = {
        "postgres":       ("#1f77b4", "o", "PostgreSQL-BYTEA", "results_postgres"),
        "postgres_minio": ("#2ca02c", "s", "PostgreSQL+MinIO", "results_postgres_minio"),
        "mongodb":        ("#d62728", "^", "MongoDB",          "results_mongo"),
    }
    _RESLABEL = {"4k": "4K", "5k": "5K", "6k": "6K"}

    def _figures(self, combined_csv: Path) -> None:
        """Publication-quality figures: log-scaled engine comparisons with std-dev
        error bars, a unity reference for storage amplification, the directly
        measured per-resolution carbon (the headline result), and a cumulative
        carbon breakdown. Robust to missing per-resolution summaries."""
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except Exception as exc:
            print(f"[report] matplotlib unavailable ({type(exc).__name__}); skipping figures.")
            return

        plt.rcParams.update({
            "font.size": 11, "axes.labelsize": 12, "legend.fontsize": 9.5,
            "xtick.labelsize": 10, "ytick.labelsize": 10, "savefig.bbox": "tight",
            "axes.axisbelow": True, "figure.dpi": 120,
        })
        res = list(DEFAULT_SWEEP)
        x = list(range(len(res)))
        xlabels = [self._RESLABEL.get(r, r) for r in res]
        emissions = self._emissions()
        skipped = self._skipped()

        def mean_std(key, stem, mfield, sfield):
            prefix = self._STYLE[key][3]
            ms, ss = [], []
            for r in res:
                row = _read_last(self.data_dir / f"{prefix}_{stem}_summary_{r}.csv")
                if row and row.get(mfield, "") not in ("", None):
                    ms.append(float(row[mfield]))
                    ss.append(float(row.get(sfield) or 0.0) if sfield else 0.0)
                else:
                    ms.append(None); ss.append(0.0)
            return ms, ss

        def carbon(key, r, dims):
            if (key, r) in skipped:
                return None
            vals = [emissions.get(f"{key}_{d}_{r}") for d in dims]
            return sum(v for v in vals if v is not None) if any(v is not None for v in vals) else None

        def lineplot(stem, mfield, sfield, ylabel, fname, logy=True, hline=None, note=None):
            fig, ax = plt.subplots(figsize=(6.6, 4.0))
            drew = False
            for key, (colour, marker, label, _) in self._STYLE.items():
                ms, ss = mean_std(key, stem, mfield, sfield)
                xs = [xi for xi, m in zip(x, ms) if m is not None]
                ys = [m for m in ms if m is not None]
                es = [s for m, s in zip(ms, ss) if m is not None]
                if ys:
                    ax.errorbar(xs, ys, yerr=es if any(es) else None, marker=marker, color=colour,
                                label=label, capsize=3, linewidth=1.8, markersize=6)
                    drew = True
            if not drew:
                plt.close(fig); return
            if hline is not None:
                ax.axhline(hline, linestyle="--", color="gray", linewidth=1.0, alpha=0.8)
            if logy:
                ax.set_yscale("log")
            ax.set_xticks(x); ax.set_xticklabels(xlabels)
            ax.set_xlabel("Image resolution"); ax.set_ylabel(ylabel)
            ax.grid(True, which="both", linestyle=":", alpha=0.4)
            ax.legend(frameon=False)
            if note:
                ax.annotate(note, xy=(0.99, 0.02), xycoords="axes fraction", ha="right", va="bottom",
                            fontsize=8.5, style="italic", color="#444444")
            fig.tight_layout()
            out = self.figures_dir / fname
            fig.savefig(out); plt.close(fig)
            print(f"[report] wrote {out}")

        skip_note = "MongoDB omitted at 6K (16 MB BSON bucket limit)"
        lineplot("insert", "mean_rows_per_sec", "std_rows_per_sec",
                 "Insert throughput (rows/s, log scale)", "insert_throughput.pdf", note=skip_note)
        lineplot("retrieve", "mean_latency_ms", "std_latency_ms",
                 "Full-retrieval latency (ms, log scale)", "retrieval_latency.pdf")
        lineplot("point_read", "mean_latency_ms", "std_latency_ms",
                 "Point-read latency (ms, log scale)", "point_read_latency.pdf")
        lineplot("insert", "mean_storage_amplification", "std_storage_amplification",
                 "Storage amplification (x, log scale)", "storage_amplification.pdf", hline=1.0)

        # Headline: directly measured per-resolution carbon (insert + retrieve + point-read).
        fig, ax = plt.subplots(figsize=(6.6, 4.0))
        for key, (colour, marker, label, _) in self._STYLE.items():
            xs, ys = [], []
            for xi, r in zip(x, res):
                c = carbon(key, r, ("insert", "retrieve", "point_read"))
                if c is not None:
                    xs.append(xi); ys.append(c)
            if ys:
                ax.plot(xs, ys, marker=marker, color=colour, label=label, linewidth=1.8, markersize=6)
        ax.set_yscale("log")
        ax.set_xticks(x); ax.set_xticklabels(xlabels)
        ax.set_xlabel("Image resolution"); ax.set_ylabel("Carbon per resolution (mg CO$_2$eq, log scale)")
        ax.grid(True, which="both", linestyle=":", alpha=0.4)
        ax.legend(frameon=False)
        ax.annotate(skip_note, xy=(0.99, 0.02), xycoords="axes fraction", ha="right", va="bottom",
                    fontsize=8.5, style="italic", color="#444444")
        fig.tight_layout()
        out = self.figures_dir / "carbon_per_resolution.pdf"
        fig.savefig(out); plt.close(fig)
        print(f"[report] wrote {out}")

        # Cumulative carbon over the common 360p-5K range, split insert vs read.
        common = [r for r in res if r != "6k"]
        keys = list(self._STYLE)
        ins = [sum(carbon(k, r, ("insert",)) or 0 for r in common) for k in keys]
        rd = [sum(carbon(k, r, ("retrieve", "point_read")) or 0 for r in common) for k in keys]
        if any(ins) or any(rd):
            fig, ax = plt.subplots(figsize=(5.6, 4.0))
            labels = [self._STYLE[k][2] for k in keys]
            colours = [self._STYLE[k][0] for k in keys]
            bx = list(range(len(keys)))
            ax.bar(bx, ins, color=colours, label="Insert")
            ax.bar(bx, rd, bottom=ins, color=colours, alpha=0.45, hatch="//", label="Retrieve + point-read")
            for xi, (a, b) in enumerate(zip(ins, rd)):
                ax.text(xi, a + b, f"{(a + b) / 1000:.1f} g", ha="center", va="bottom", fontsize=9)
            ax.set_xticks(bx); ax.set_xticklabels(labels, rotation=8)
            ax.set_ylabel("Cumulative carbon, 360p--5K (mg CO$_2$eq)")
            ax.legend(frameon=False)
            ax.grid(True, axis="y", linestyle=":", alpha=0.4)
            fig.tight_layout()
            out = self.figures_dir / "carbon_breakdown.pdf"
            fig.savefig(out); plt.close(fig)
            print(f"[report] wrote {out}")


if __name__ == "__main__":
    Reporter(Locations.create()).build()
