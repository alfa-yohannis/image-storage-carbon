import importlib.util
import inspect
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BENCHMARK_DATA_DIR", str(Path(tempfile.gettempdir()) / "iotbench_test" / "data"))
os.environ.setdefault("BENCHMARK_FIGURES_DIR", str(Path(tempfile.gettempdir()) / "iotbench_test" / "figures"))

_DRIVERS = ("psycopg2", "pymongo", "minio")
_HAVE_DRIVERS = all(importlib.util.find_spec(m) is not None for m in _DRIVERS)


@unittest.skipUnless(_HAVE_DRIVERS, "DB drivers (psycopg2/pymongo/minio) not installed")
class TestEngineContract(unittest.TestCase):
    def test_engines_are_concrete_and_well_formed(self):
        from config import Settings
        from engine_mongodb import MongoEngine
        from engine_postgres import PostgresEngine
        from engine_postgres_minio import PostgresMinioEngine

        expected = {
            PostgresEngine: ("postgres", ("timescaledb",)),
            PostgresMinioEngine: ("postgres_minio", ("timescaledb", "minio")),
            MongoEngine: ("mongodb", ("mongodb",)),
        }
        settings = Settings.load("360p_sd_image")
        for cls, (name, services) in expected.items():
            self.assertFalse(inspect.isabstract(cls), f"{cls.__name__} is still abstract")
            self.assertEqual(cls.name, name)
            self.assertEqual(cls.services, services)
            self.assertTrue(cls.csv_prefix.startswith("results_"))
            engine = cls(settings)  # constructor must not touch the network
            self.assertIs(engine.settings, settings)


if __name__ == "__main__":
    unittest.main()
