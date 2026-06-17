import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from carbon import CarbonTracker


class TestCarbonTracker(unittest.TestCase):
    def test_disabled_is_noop(self):
        tmp = Path(tempfile.mkdtemp(prefix="iotbench_carbon_"))
        with CarbonTracker("unit_test", tmp, enabled=False) as tracker:
            self.assertIsInstance(tracker, CarbonTracker)
        # disabled tracker must not write an emissions file
        self.assertFalse((tmp / "emissions.csv").exists())

    def test_exceptions_propagate(self):
        tmp = Path(tempfile.mkdtemp(prefix="iotbench_carbon_"))
        with self.assertRaises(ValueError):
            with CarbonTracker("unit_test", tmp, enabled=False):
                raise ValueError("boom")


if __name__ == "__main__":
    unittest.main()
