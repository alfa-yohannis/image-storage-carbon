import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
os.environ.setdefault("BENCHMARK_DATA_DIR", str(Path(tempfile.gettempdir()) / "iotbench_test" / "data"))
os.environ.setdefault("BENCHMARK_FIGURES_DIR", str(Path(tempfile.gettempdir()) / "iotbench_test" / "figures"))


class TestPayloads(unittest.TestCase):
    def test_build_image_payload(self):
        from config import Locations, resolve_profile
        from payloads import PayloadFactory
        loc = Locations.create()
        factory = PayloadFactory(loc.source_image_path)
        payload = factory.build(resolve_profile("360p_sd_image"))
        self.assertEqual((payload.width, payload.height), (640, 360))
        self.assertGreater(payload.payload_size_bytes, 0)
        self.assertEqual(payload.payload_bytes[:2], b"\xff\xd8")  # JPEG start-of-image
        self.assertEqual(payload.mime_type, "image/jpeg")
        self.assertAlmostEqual(payload.payload_size_mb,
                               payload.payload_size_bytes / (1024 * 1024), places=6)

    def test_larger_resolution_is_bigger(self):
        from config import Locations, resolve_profile
        from payloads import PayloadFactory
        factory = PayloadFactory(Locations.create().source_image_path)
        small = factory.build(resolve_profile("360p_sd_image"))
        large = factory.build(resolve_profile("1080p_fhd_image"))
        self.assertGreater(large.payload_size_bytes, small.payload_size_bytes)


if __name__ == "__main__":
    unittest.main()
