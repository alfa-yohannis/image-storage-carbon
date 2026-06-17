"""pytest bootstrap: make code/ importable and route test outputs to a temp dir."""
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
_tmp = Path(tempfile.gettempdir()) / "iotbench_test"
os.environ.setdefault("BENCHMARK_DATA_DIR", str(_tmp / "data"))
os.environ.setdefault("BENCHMARK_FIGURES_DIR", str(_tmp / "figures"))
