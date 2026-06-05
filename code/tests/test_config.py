import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BENCHMARK_DATA_DIR", str(Path(tempfile.gettempdir()) / "iotbench_test" / "data"))
os.environ.setdefault("BENCHMARK_FIGURES_DIR", str(Path(tempfile.gettempdir()) / "iotbench_test" / "figures"))


class TestConfig(unittest.TestCase):
    def test_default_sweep_resolves(self):
        from config import DEFAULT_SWEEP, resolve_profile
        for p in DEFAULT_SWEEP:
            self.assertEqual(resolve_profile(p).name, p)

    def test_sweep_spans_360p_to_6k(self):
        from config import DEFAULT_SWEEP, WORKLOAD_PROFILES
        self.assertEqual(len(DEFAULT_SWEEP), 8)
        first, last = WORKLOAD_PROFILES[DEFAULT_SWEEP[0]], WORKLOAD_PROFILES[DEFAULT_SWEEP[-1]]
        self.assertEqual((first.width, first.height), (640, 360))
        self.assertEqual((last.width, last.height), (6144, 3456))

    def test_canonical_names_are_short(self):
        from config import resolve_profile
        self.assertEqual(resolve_profile("360p").name, "360p")
        self.assertEqual(resolve_profile("1080p").name, "1080p")
        self.assertEqual(resolve_profile("4k").name, "4k")
        self.assertEqual(resolve_profile("6k").name, "6k")
        self.assertEqual(resolve_profile("4K").name, "4k")  # case-insensitive

    def test_legacy_long_keys_are_aliases(self):
        from config import resolve_profile
        self.assertEqual(resolve_profile("6k_uhd_image").name, "6k")
        self.assertEqual(resolve_profile("5k_image").name, "5k")
        self.assertEqual(resolve_profile("360p_sd_image").name, "360p")
        self.assertEqual(resolve_profile("large_fhd_image").name, "1080p")

    def test_unknown_profile_raises(self):
        from config import resolve_profile
        with self.assertRaises(ValueError):
            resolve_profile("does_not_exist")

    def test_settings_load_routes_outputs(self):
        from config import Settings
        s = Settings.load("1080p_fhd_image")
        self.assertEqual(s.workload.width, 1920)
        # data/ and figures/ live next to code/ (the ESD root), and are created
        self.assertEqual(s.locations.data_dir.name, "data")
        self.assertEqual(s.locations.figures_dir.name, "figures")
        self.assertTrue(s.locations.data_dir.exists())
        self.assertTrue(s.locations.figures_dir.exists())

    def test_default_routing_is_sibling_of_code(self):
        # With no env override, data/ and figures/ sit next to code/ (the ESD root).
        from config import Locations
        saved = {k: os.environ.pop(k, None) for k in ("BENCHMARK_DATA_DIR", "BENCHMARK_FIGURES_DIR")}
        try:
            loc = Locations.create()
            self.assertEqual(loc.data_dir, loc.code_dir.parent / "data")
            self.assertEqual(loc.figures_dir, loc.code_dir.parent / "figures")
        finally:
            for key, value in saved.items():
                if value is not None:
                    os.environ[key] = value

    def test_with_profile(self):
        from config import Settings
        s = Settings.load("1080p").with_profile("4k")
        self.assertEqual(s.profile_slug, "4k")
        self.assertEqual(s.workload.width, 3840)


if __name__ == "__main__":
    unittest.main()
