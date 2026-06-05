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

    def build(self) -> Path:
        emissions = self._emissions()
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

    def _figures(self, combined_csv: Path) -> None:
        try:
            import matplotlib
            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except Exception as exc:
            print(f"[report] matplotlib unavailable ({type(exc).__name__}); skipping figures.")
            return

        with combined_csv.open(newline="") as handle:
            rows = list(csv.DictReader(handle))
        profiles = [r["profile"].replace("_image", "").replace("_sd", "").replace("_hd", "")
                    .replace("_fhd", "").replace("_qhd", "").replace("_uhd", "") for r in rows]

        def col(key: str) -> list[float | None]:
            vals = []
            for r in rows:
                v = r.get(key, "")
                vals.append(float(v) if v not in ("", None) else None)
            return vals

        panels = [
            ("insert_rows_per_sec", "Insert throughput (rows/s)", "insert_throughput.pdf"),
            ("point_read_ms", "Point-read latency (ms)", "point_read_latency.pdf"),
            ("storage_amp", "Storage amplification (x)", "storage_amplification.pdf"),
            ("carbon_mg", "Carbon per resolution (mg CO2eq)", "carbon_per_resolution.pdf"),
        ]
        for metric, ylabel, fname in panels:
            fig, ax = plt.subplots(figsize=(7, 4))
            plotted = False
            for key, label, _ in ENGINES:
                ys = col(f"{key}_{metric}")
                xs = [p for p, y in zip(profiles, ys) if y is not None]
                yy = [y for y in ys if y is not None]
                if yy:
                    ax.plot(xs, yy, marker="o", label=label)
                    plotted = True
            if not plotted:
                plt.close(fig)
                continue
            ax.set_xlabel("Resolution")
            ax.set_ylabel(ylabel)
            ax.set_title(ylabel)
            ax.legend()
            ax.grid(True, alpha=0.3)
            fig.tight_layout()
            out = self.figures_dir / fname
            fig.savefig(out)
            plt.close(fig)
            print(f"[report] wrote {out}")


if __name__ == "__main__":
    Reporter(Locations.create()).build()
