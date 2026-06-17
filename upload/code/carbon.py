"""CodeCarbon wrapper.

`CarbonTracker` is a context manager that measures the energy / CO2 of the work
done inside the `with` block and appends one row to `<data_dir>/emissions.csv`
tagged with `project_name`. CodeCarbon is imported lazily so the rest of the
harness imports cleanly even when CodeCarbon is not installed; in that case the
tracker degrades to a no-op (with a warning).
"""
from __future__ import annotations

from pathlib import Path


class CarbonTracker:
    def __init__(self, project_name: str, data_dir: Path, enabled: bool = True):
        self.project_name = project_name
        self.data_dir = Path(data_dir)
        self.enabled = enabled
        self._tracker = None

    def __enter__(self) -> "CarbonTracker":
        if not self.enabled:
            return self
        try:
            from codecarbon import EmissionsTracker
        except Exception as exc:  # codecarbon missing or import error
            print(f"[carbon] disabled ({type(exc).__name__}): {exc}")
            self.enabled = False
            return self
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._tracker = EmissionsTracker(
            project_name=self.project_name,
            output_dir=str(self.data_dir),
            log_level="warning",
        )
        self._tracker.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if self._tracker is not None:
            self._tracker.stop()
            self._tracker = None
        return False  # never suppress exceptions
