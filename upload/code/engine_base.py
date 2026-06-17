"""Storage-engine abstraction (Strategy) + measurement protocol (Template Method).

`StorageEngine` defines the shared benchmark protocol (warm-up, run counts,
timing, aggregation) in concrete `run_*` methods, and delegates the
engine-specific work to small abstract primitives implemented by each concrete
engine (PostgresEngine, PostgresMinioEngine, MongoEngine).
"""
from __future__ import annotations

import abc
import statistics
import time
from dataclasses import dataclass, field

from config import Settings
from payloads import MediaPayload


def mean_std(values: list[float]) -> tuple[float, float]:
    if not values:
        return 0.0, 0.0
    mean = statistics.mean(values)
    std = statistics.stdev(values) if len(values) > 1 else 0.0
    return mean, std


# --------------------------------------------------------------------------- #
# Result value objects
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class StorageSizes:
    table_total_bytes: int
    table_data_bytes: int
    table_index_bytes: int
    db_bytes: int


@dataclass(frozen=True)
class InsertRun:
    duration_sec: float
    rows_inserted: int
    rows_in_table_after: int
    before: StorageSizes
    after: StorageSizes


@dataclass(frozen=True)
class InsertResult:
    runs: list[InsertRun] = field(default_factory=list)


@dataclass(frozen=True)
class LatencyResult:
    latencies_ms: list[float] = field(default_factory=list)
    meta: dict = field(default_factory=dict)


# --------------------------------------------------------------------------- #
# Engine base
# --------------------------------------------------------------------------- #
class StorageEngine(abc.ABC):
    #: short tag used in CodeCarbon project names, e.g. "postgres"
    name: str = "engine"
    #: descriptive label written to the "engine" CSV column
    engine_label: str = "engine"
    #: CSV filename prefix for insert/retrieve/point_read, e.g. "results_postgres"
    csv_prefix: str = "results_engine"
    #: driver-summary CSV stem (no profile suffix), e.g. "results_postgres_driver_summary"
    driver_csv_stem: str = "results_engine_driver_summary"
    driver_query_id: str = "Q_driver_roundtrip"
    #: docker-compose services this engine needs
    services: tuple[str, ...] = ()

    def __init__(self, settings: Settings):
        self.settings = settings

    # ---- lifecycle (abstract) ------------------------------------------- #
    @abc.abstractmethod
    def wait_ready(self) -> None: ...

    def close(self) -> None:  # optional override
        return None

    # ---- insert primitives (abstract) ----------------------------------- #
    @abc.abstractmethod
    def _reset(self) -> None:
        """Drop and recreate the table/collection (+ bucket) for a fresh run."""

    @abc.abstractmethod
    def _insert_rows(self, payload: MediaPayload, n_rows: int, batch_size: int) -> tuple[int, float]:
        """Insert n_rows; return (rows_inserted, measured_duration_sec)."""

    @abc.abstractmethod
    def _storage_sizes(self) -> StorageSizes: ...

    @abc.abstractmethod
    def _row_count(self) -> int: ...

    # ---- retrieval primitives ------------------------------------------- #
    @abc.abstractmethod
    def _retrieval_prepare(self) -> bool:
        """Open a session and cache the time range. Return False if no data."""

    @abc.abstractmethod
    def _retrieval_once(self) -> tuple[int, int]:
        """Materialise all payloads in range; return (rows_returned, total_bytes)."""

    def _retrieval_finish(self) -> None:
        return None

    # ---- point-read primitives ------------------------------------------ #
    def _point_read_prepare(self) -> None:
        return None

    @abc.abstractmethod
    def _point_read_once(self) -> None:
        """Fetch the latest payload for the device and touch its bytes."""

    def _point_read_finish(self) -> None:
        return None

    # ---- driver primitives ---------------------------------------------- #
    def _driver_prepare(self) -> None:
        return None

    @abc.abstractmethod
    def _driver_once(self) -> None:
        """Issue one minimal client/server round-trip."""

    def _driver_finish(self) -> None:
        return None

    # ---- measurement protocol (template methods) ------------------------ #
    def run_insert(self, payload: MediaPayload) -> InsertResult:
        s = self.settings
        if s.warmup_rows > 0:
            self._reset()
            self._insert_rows(payload, s.warmup_rows, s.batch_size)
        runs: list[InsertRun] = []
        for i in range(1, s.insert_runs + 1):
            self._reset()
            before = self._storage_sizes()
            rows, duration = self._insert_rows(payload, s.total_rows, s.batch_size)
            after = self._storage_sizes()
            count = self._row_count()
            runs.append(InsertRun(duration, rows, count, before, after))
            print(f"  [{self.name}] insert run {i}/{s.insert_runs}: "
                  f"{(rows / duration if duration else 0):.2f} rows/s")
        return InsertResult(runs)

    def run_retrieval(self) -> LatencyResult:
        s = self.settings
        meta = {"rows_returned": 0, "total_bytes_returned": 0,
                "query_id": "Q_retrieve_binaries_time_range"}
        if not self._retrieval_prepare():
            print(f"  [{self.name}] retrieval skipped: no data")
            return LatencyResult([], meta)
        latencies: list[float] = []
        try:
            for _ in range(s.aggregation_warmup_runs):
                self._retrieval_once()
            for i in range(1, s.aggregation_runs + 1):
                t0 = time.perf_counter()
                rows, total = self._retrieval_once()
                latencies.append((time.perf_counter() - t0) * 1000.0)
                meta["rows_returned"], meta["total_bytes_returned"] = rows, total
                print(f"  [{self.name}] retrieve run {i}/{s.aggregation_runs}: {latencies[-1]:.1f} ms")
        finally:
            self._retrieval_finish()
        return LatencyResult(latencies, meta)

    def run_point_read(self, payload: MediaPayload) -> LatencyResult:
        s = self.settings
        self._point_read_prepare()
        latencies: list[float] = []
        try:
            for _ in range(s.point_read_warmup_runs):
                self._point_read_once()
            for i in range(1, s.point_read_runs + 1):
                t0 = time.perf_counter()
                self._point_read_once()
                latencies.append((time.perf_counter() - t0) * 1000.0)
        finally:
            self._point_read_finish()
        return LatencyResult(
            latencies,
            {"payload_size_bytes": payload.payload_size_bytes, "query_id": "Q_latest_payload_by_device"},
        )

    def run_driver(self) -> LatencyResult:
        s = self.settings
        self._driver_prepare()
        latencies: list[float] = []
        try:
            for _ in range(s.driver_warmup_runs):
                self._driver_once()
            for _ in range(s.driver_runs):
                t0 = time.perf_counter()
                self._driver_once()
                latencies.append((time.perf_counter() - t0) * 1000.0)
        finally:
            self._driver_finish()
        return LatencyResult(latencies, {"query_id": self.driver_query_id})
