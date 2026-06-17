import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BENCHMARK_DATA_DIR", str(Path(tempfile.gettempdir()) / "iotbench_test" / "data"))
os.environ.setdefault("BENCHMARK_FIGURES_DIR", str(Path(tempfile.gettempdir()) / "iotbench_test" / "figures"))

from config import Locations
from report import Reporter


def _write_csv(path: Path, fieldnames, rows):
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


class TestReporterSkips(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iotbench_report_"))
        self.data = self.tmp / "data"
        self.figs = self.tmp / "figures"
        self.data.mkdir(parents=True)
        self.figs.mkdir(parents=True)
        self.loc = Locations(code_dir=self.tmp, esd_root=self.tmp, data_dir=self.data,
                             figures_dir=self.figs, assets_dir=self.tmp,
                             source_image_path=self.tmp / "x.jpg")

    def _row_for(self, combined: Path, profile: str) -> dict:
        rows = {r["profile"]: r for r in csv.DictReader(combined.open())}
        return rows[profile]

    def test_skipped_cell_is_blank_even_with_stray_emissions(self):
        # MongoDB 6k was skipped after repeated failures ...
        _write_csv(self.data / "skipped.csv",
                   ["timestamp", "engine", "profile", "payload_kind", "payload_size_bytes",
                    "payload_size_mb", "attempts", "error_type", "error"],
                   [{"timestamp": "t", "engine": "mongodb", "profile": "6k", "payload_kind": "image",
                     "payload_size_bytes": 0, "payload_size_mb": 0, "attempts": 2,
                     "error_type": "DocumentTooLarge", "error": "BSON limit"}])
        # ... yet a failed attempt left a stray carbon row for that exact cell.
        _write_csv(self.data / "emissions.csv", ["project_name", "emissions"],
                   [{"project_name": "mongodb_insert_6k", "emissions": "0.001"}])

        combined = Reporter(self.loc).build()
        row = self._row_for(combined, "6k")
        self.assertEqual(row["mongodb_carbon_mg"], "")          # stray emissions excluded
        self.assertEqual(row["mongodb_insert_rows_per_sec"], "")
        self.assertEqual(row["mongodb_point_read_ms"], "")

    def test_non_skipped_cell_still_reports_carbon(self):
        _write_csv(self.data / "emissions.csv", ["project_name", "emissions"],
                   [{"project_name": "postgres_insert_6k", "emissions": "0.002"}])
        combined = Reporter(self.loc).build()
        row = self._row_for(combined, "6k")
        self.assertNotEqual(row["postgres_carbon_mg"], "")      # 0.002 kg -> 2000 mg
        self.assertAlmostEqual(float(row["postgres_carbon_mg"]), 2000.0, places=1)


if __name__ == "__main__":
    unittest.main()
