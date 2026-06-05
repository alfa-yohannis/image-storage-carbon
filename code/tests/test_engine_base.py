import os
import sys
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BENCHMARK_DATA_DIR", str(Path(tempfile.gettempdir()) / "iotbench_test" / "data"))
os.environ.setdefault("BENCHMARK_FIGURES_DIR", str(Path(tempfile.gettempdir()) / "iotbench_test" / "figures"))

from config import Settings
from engine_base import StorageEngine, StorageSizes
from payloads import MediaPayload


class FakeEngine(StorageEngine):
    name = "fake"
    engine_label = "fake"
    csv_prefix = "results_fake"
    driver_csv_stem = "results_fake_driver_summary"
    driver_query_id = "Q_fake"
    services = ()

    def __init__(self, settings):
        super().__init__(settings)
        self.rows = 0
        self.reset_count = self.insert_calls = 0
        self.retr_calls = self.pr_calls = self.drv_calls = 0

    def wait_ready(self):
        pass

    def _reset(self):
        self.reset_count += 1
        self.rows = 0

    def _insert_rows(self, payload, n_rows, batch_size):
        self.insert_calls += 1
        self.rows = n_rows
        return n_rows, 0.001

    def _storage_sizes(self):
        return StorageSizes(self.rows, self.rows, 0, self.rows)

    def _row_count(self):
        return self.rows

    def _retrieval_prepare(self):
        return self.rows > 0

    def _retrieval_once(self):
        self.retr_calls += 1
        return self.rows, self.rows * 10

    def _point_read_once(self):
        self.pr_calls += 1

    def _driver_once(self):
        self.drv_calls += 1


def _payload():
    return MediaPayload("360p_sd_image", "image", "image/jpeg", "jpeg", 640, 360, 0, b"x" * 100)


def _settings():
    return replace(
        Settings.load("360p_sd_image"),
        insert_runs=3, warmup_rows=10, total_rows=100, batch_size=50,
        aggregation_runs=4, aggregation_warmup_runs=2,
        point_read_runs=5, point_read_warmup_runs=1,
        driver_runs=6, driver_warmup_runs=2,
    )


class TestMeasurementProtocol(unittest.TestCase):
    def setUp(self):
        self.engine = FakeEngine(_settings())

    def test_run_insert(self):
        result = self.engine.run_insert(_payload())
        self.assertEqual(len(result.runs), 3)
        self.assertTrue(all(r.rows_inserted == 100 for r in result.runs))
        self.assertEqual(self.engine.reset_count, 4)   # 1 warm-up + 3 measured
        self.assertEqual(self.engine.insert_calls, 4)

    def test_run_retrieval_with_data(self):
        self.engine.rows = 100
        result = self.engine.run_retrieval()
        self.assertEqual(len(result.latencies_ms), 4)  # aggregation_runs
        self.assertEqual(self.engine.retr_calls, 6)    # 2 warm-up + 4 measured
        self.assertEqual(result.meta["rows_returned"], 100)

    def test_run_retrieval_no_data_is_empty(self):
        self.engine.rows = 0
        result = self.engine.run_retrieval()
        self.assertEqual(result.latencies_ms, [])

    def test_run_point_read(self):
        result = self.engine.run_point_read(_payload())
        self.assertEqual(len(result.latencies_ms), 5)
        self.assertEqual(self.engine.pr_calls, 6)      # 1 warm-up + 5 measured

    def test_run_driver(self):
        result = self.engine.run_driver()
        self.assertEqual(len(result.latencies_ms), 6)
        self.assertEqual(self.engine.drv_calls, 8)     # 2 warm-up + 6 measured


if __name__ == "__main__":
    unittest.main()
