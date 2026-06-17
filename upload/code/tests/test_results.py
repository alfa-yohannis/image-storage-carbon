import csv
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BENCHMARK_DATA_DIR", str(Path(tempfile.gettempdir()) / "iotbench_test" / "data"))
os.environ.setdefault("BENCHMARK_FIGURES_DIR", str(Path(tempfile.gettempdir()) / "iotbench_test" / "figures"))

from config import Settings
from engine_base import InsertResult, InsertRun, LatencyResult, StorageSizes
from payloads import MediaPayload
from results import ResultWriter


class _FakeEngine:
    """Minimal engine-like object exposing the metadata the writer reads."""
    name = "fake"
    engine_label = "fake-engine"
    csv_prefix = "results_fake"
    driver_csv_stem = "results_fake_driver_summary"
    driver_query_id = "Q_fake"


class TestResultWriter(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="iotbench_res_"))
        self.writer = ResultWriter(self.tmp)
        self.settings = Settings.load("360p")
        self.payload = MediaPayload("360p", "image", "image/jpeg", "jpeg", 640, 360, 0, b"x" * 1000)
        self.engine = _FakeEngine()

    def test_write_insert_computes_metrics(self):
        before = StorageSizes(0, 0, 0, 0)
        after = StorageSizes(2 * 1024 * 1024, 2 * 1024 * 1024, 0, 3 * 1024 * 1024)
        run = InsertRun(duration_sec=0.5, rows_inserted=2000, rows_in_table_after=2000, before=before, after=after)
        self.writer.write_insert(self.engine, self.settings, self.payload, InsertResult([run]))

        runs_csv = self.tmp / "results_fake_insert_runs_360p.csv"
        summary_csv = self.tmp / "results_fake_insert_summary_360p.csv"
        self.assertTrue(runs_csv.exists())
        self.assertTrue(summary_csv.exists())
        row = list(csv.DictReader(runs_csv.open()))[0]
        self.assertAlmostEqual(float(row["rows_per_sec"]), 4000.0, places=1)        # 2000 / 0.5
        self.assertGreater(float(row["table_storage_amplification"]), 1.0)          # 2MB on-disk > ~1.9MB logical
        self.assertEqual(int(row["rows_in_table_after"]), 2000)

    def test_write_retrieval_summary_mean(self):
        res = LatencyResult([10.0, 12.0, 14.0],
                            {"query_id": "Q", "rows_returned": 100, "total_bytes_returned": 1000})
        self.writer.write_retrieval(self.engine, self.settings, self.payload, res)
        summary = self.tmp / "results_fake_retrieve_summary_360p.csv"
        self.assertTrue(summary.exists())
        row = list(csv.DictReader(summary.open()))[0]
        self.assertAlmostEqual(float(row["mean_latency_ms"]), 12.0, places=3)
        self.assertEqual(int(row["rows_returned"]), 100)

    def test_write_driver_summary(self):
        res = LatencyResult([0.10, 0.20], {"query_id": "Q_fake"})
        self.writer.write_driver(self.engine, self.settings, res)
        driver_csv = self.tmp / "results_fake_driver_summary.csv"
        self.assertTrue(driver_csv.exists())
        row = list(csv.DictReader(driver_csv.open()))[0]
        self.assertEqual(int(row["n_runs"]), 2)
        self.assertEqual(row["profile"], "360p")

    def test_write_skip_records_failure(self):
        err = ValueError("payload exceeds 16 MiB BSON document limit")
        self.writer.write_skip(self.engine, self.settings, self.payload, attempts=2, error=err)
        skip_csv = self.tmp / "skipped.csv"
        self.assertTrue(skip_csv.exists())
        row = list(csv.DictReader(skip_csv.open()))[0]
        self.assertEqual(row["engine"], "fake")          # registry tag, not engine_label
        self.assertEqual(row["profile"], "360p")
        self.assertEqual(int(row["attempts"]), 2)
        self.assertEqual(row["error_type"], "ValueError")
        self.assertIn("BSON", row["error"])


if __name__ == "__main__":
    unittest.main()
