"""CSV result writer. Filenames keep the original per-paper stems so existing
analyses keep working; everything lands in the ESD `data/` directory."""
from __future__ import annotations

import csv
from datetime import datetime, timezone
from pathlib import Path

from config import Settings
from engine_base import InsertResult, LatencyResult, StorageEngine, mean_std
from payloads import MediaPayload


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _mb(value: float) -> float:
    return float(value) / (1024 * 1024)


def _append(path: Path, fieldnames: list[str], row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if not exists:
            writer.writeheader()
        writer.writerow(row)


_INSERT_RUN_FIELDS = [
    "timestamp", "engine", "profile", "payload_kind", "payload_size_bytes", "payload_size_mb",
    "run_id", "total_rows_requested", "rows_inserted", "batch_size", "duration_sec", "rows_per_sec",
    "logical_mb_inserted", "logical_mb_per_sec", "db_size_before_mb", "db_size_after_mb",
    "table_total_before_mb", "table_total_after_mb", "table_data_before_mb", "table_data_after_mb",
    "table_index_before_mb", "table_index_after_mb", "rows_in_table_after", "table_storage_amplification",
]
_INSERT_SUMMARY_FIELDS = [
    "timestamp", "engine", "profile", "payload_kind", "payload_size_bytes", "payload_size_mb",
    "warmup_rows", "total_rows_per_run", "batch_size", "n_runs",
    "mean_duration_sec", "std_duration_sec", "mean_rows_per_sec", "std_rows_per_sec",
    "mean_logical_mb_per_sec", "std_logical_mb_per_sec", "mean_db_size_after_mb", "std_db_size_after_mb",
    "mean_table_total_after_mb", "std_table_total_after_mb", "mean_storage_amplification", "std_storage_amplification",
]
_RETRIEVE_RUN_FIELDS = [
    "timestamp", "engine", "profile", "payload_kind", "query_id", "run_id",
    "latency_ms", "rows_returned", "total_bytes_returned",
]
_RETRIEVE_SUMMARY_FIELDS = [
    "timestamp", "engine", "profile", "payload_kind", "query_id",
    "mean_latency_ms", "std_latency_ms", "n_runs", "rows_returned", "total_bytes_returned",
]
_POINT_READ_RUN_FIELDS = [
    "timestamp", "engine", "profile", "payload_kind", "query_id", "run_id", "latency_ms", "payload_size_bytes",
]
_POINT_READ_SUMMARY_FIELDS = [
    "timestamp", "engine", "profile", "payload_kind", "query_id",
    "mean_latency_ms", "std_latency_ms", "n_runs", "payload_size_bytes",
]
_DRIVER_SUMMARY_FIELDS = [
    "timestamp", "engine", "profile", "query_id", "mean_latency_ms", "std_latency_ms", "n_runs",
]
_SKIP_FIELDS = [
    "timestamp", "engine", "profile", "payload_kind", "payload_size_bytes", "payload_size_mb",
    "attempts", "error_type", "error",
]


class ResultWriter:
    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)

    def _profile_csv(self, stem: str, profile: str) -> Path:
        return self.data_dir / f"{stem}_{profile}.csv"

    # ---- insert --------------------------------------------------------- #
    def write_insert(self, engine: StorageEngine, settings: Settings,
                     payload: MediaPayload, result: InsertResult) -> None:
        profile = settings.profile_slug
        run_csv = self._profile_csv(f"{engine.csv_prefix}_insert_runs", profile)
        summary_csv = self._profile_csv(f"{engine.csv_prefix}_insert_summary", profile)

        rows_per_sec, mb_per_sec, db_after, table_after, amp = [], [], [], [], []
        for i, run in enumerate(result.runs, start=1):
            logical_mb = _mb(run.rows_inserted * payload.payload_size_bytes)
            rps = run.rows_inserted / run.duration_sec if run.duration_sec else 0.0
            mbps = logical_mb / run.duration_sec if run.duration_sec else 0.0
            table_total_after_mb = _mb(run.after.table_total_bytes)
            amplification = table_total_after_mb / logical_mb if logical_mb else 0.0
            rows_per_sec.append(rps); mb_per_sec.append(mbps)
            db_after.append(_mb(run.after.db_bytes)); table_after.append(table_total_after_mb)
            amp.append(amplification)
            _append(run_csv, _INSERT_RUN_FIELDS, {
                "timestamp": _now(), "engine": engine.engine_label, "profile": profile,
                "payload_kind": payload.payload_kind, "payload_size_bytes": payload.payload_size_bytes,
                "payload_size_mb": round(payload.payload_size_mb, 6), "run_id": i,
                "total_rows_requested": settings.total_rows, "rows_inserted": run.rows_inserted,
                "batch_size": settings.batch_size, "duration_sec": round(run.duration_sec, 4),
                "rows_per_sec": round(rps, 2), "logical_mb_inserted": round(logical_mb, 3),
                "logical_mb_per_sec": round(mbps, 3),
                "db_size_before_mb": round(_mb(run.before.db_bytes), 3),
                "db_size_after_mb": round(_mb(run.after.db_bytes), 3),
                "table_total_before_mb": round(_mb(run.before.table_total_bytes), 3),
                "table_total_after_mb": round(table_total_after_mb, 3),
                "table_data_before_mb": round(_mb(run.before.table_data_bytes), 3),
                "table_data_after_mb": round(_mb(run.after.table_data_bytes), 3),
                "table_index_before_mb": round(_mb(run.before.table_index_bytes), 3),
                "table_index_after_mb": round(_mb(run.after.table_index_bytes), 3),
                "rows_in_table_after": run.rows_in_table_after,
                "table_storage_amplification": round(amplification, 4),
            })

        durations = [r.duration_sec for r in result.runs]
        m_dur, s_dur = mean_std(durations)
        m_rps, s_rps = mean_std(rows_per_sec)
        m_mbps, s_mbps = mean_std(mb_per_sec)
        m_db, s_db = mean_std(db_after)
        m_tbl, s_tbl = mean_std(table_after)
        m_amp, s_amp = mean_std(amp)
        _append(summary_csv, _INSERT_SUMMARY_FIELDS, {
            "timestamp": _now(), "engine": engine.engine_label, "profile": profile,
            "payload_kind": payload.payload_kind, "payload_size_bytes": payload.payload_size_bytes,
            "payload_size_mb": round(payload.payload_size_mb, 6), "warmup_rows": settings.warmup_rows,
            "total_rows_per_run": settings.total_rows, "batch_size": settings.batch_size,
            "n_runs": len(result.runs),
            "mean_duration_sec": round(m_dur, 4), "std_duration_sec": round(s_dur, 4),
            "mean_rows_per_sec": round(m_rps, 2), "std_rows_per_sec": round(s_rps, 2),
            "mean_logical_mb_per_sec": round(m_mbps, 3), "std_logical_mb_per_sec": round(s_mbps, 3),
            "mean_db_size_after_mb": round(m_db, 3), "std_db_size_after_mb": round(s_db, 3),
            "mean_table_total_after_mb": round(m_tbl, 3), "std_table_total_after_mb": round(s_tbl, 3),
            "mean_storage_amplification": round(m_amp, 4), "std_storage_amplification": round(s_amp, 4),
        })
        print(f"  [{engine.name}] insert summary: {m_rps:.2f} rows/s, amp {m_amp:.2f}x")

    # ---- retrieval (full materialisation) ------------------------------- #
    def write_retrieval(self, engine: StorageEngine, settings: Settings,
                        payload: MediaPayload, result: LatencyResult) -> None:
        self._write_latency(
            engine, settings, payload, result,
            stem=f"{engine.csv_prefix}_retrieve",
            run_fields=_RETRIEVE_RUN_FIELDS, summary_fields=_RETRIEVE_SUMMARY_FIELDS,
            extra_run=lambda: {"rows_returned": result.meta.get("rows_returned", 0),
                               "total_bytes_returned": result.meta.get("total_bytes_returned", 0)},
            extra_summary=lambda: {"rows_returned": result.meta.get("rows_returned", 0),
                                   "total_bytes_returned": result.meta.get("total_bytes_returned", 0)},
        )

    # ---- point read ----------------------------------------------------- #
    def write_point_read(self, engine: StorageEngine, settings: Settings,
                         payload: MediaPayload, result: LatencyResult) -> None:
        self._write_latency(
            engine, settings, payload, result,
            stem=f"{engine.csv_prefix}_point_read",
            run_fields=_POINT_READ_RUN_FIELDS, summary_fields=_POINT_READ_SUMMARY_FIELDS,
            extra_run=lambda: {"payload_size_bytes": payload.payload_size_bytes},
            extra_summary=lambda: {"payload_size_bytes": payload.payload_size_bytes},
        )

    def _write_latency(self, engine, settings, payload, result, stem,
                       run_fields, summary_fields, extra_run, extra_summary) -> None:
        profile = settings.profile_slug
        query_id = result.meta.get("query_id", "")
        run_csv = self._profile_csv(f"{stem}_runs", profile)
        summary_csv = self._profile_csv(f"{stem}_summary", profile)
        for i, latency in enumerate(result.latencies_ms, start=1):
            row = {"timestamp": _now(), "engine": engine.engine_label, "profile": profile,
                   "payload_kind": payload.payload_kind, "query_id": query_id, "run_id": i,
                   "latency_ms": round(latency, 3)}
            row.update(extra_run())
            _append(run_csv, run_fields, row)
        m, s = mean_std(result.latencies_ms)
        summary = {"timestamp": _now(), "engine": engine.engine_label, "profile": profile,
                   "payload_kind": payload.payload_kind, "query_id": query_id,
                   "mean_latency_ms": round(m, 3), "std_latency_ms": round(s, 3),
                   "n_runs": len(result.latencies_ms)}
        summary.update(extra_summary())
        _append(summary_csv, summary_fields, summary)
        print(f"  [{engine.name}] {stem.split('_')[-1]} summary: {m:.3f} +/- {s:.3f} ms")

    # ---- skipped cell --------------------------------------------------- #
    def write_skip(self, engine: StorageEngine, settings: Settings, payload: MediaPayload,
                   attempts: int, error: BaseException) -> None:
        """Record an (engine, resolution) cell that was skipped after repeated
        measurement failures. `engine` is the registry tag (e.g. "mongodb") so
        the reporter can exclude it; the error string is truncated for tidiness."""
        _append(self.data_dir / "skipped.csv", _SKIP_FIELDS, {
            "timestamp": _now(), "engine": engine.name, "profile": settings.profile_slug,
            "payload_kind": payload.payload_kind, "payload_size_bytes": payload.payload_size_bytes,
            "payload_size_mb": round(payload.payload_size_mb, 6), "attempts": attempts,
            "error_type": type(error).__name__, "error": str(error)[:500],
        })
        print(f"  [{engine.name}] {settings.profile_slug} skipped after {attempts} attempt(s): "
              f"{type(error).__name__}")

    # ---- driver overhead ------------------------------------------------ #
    def write_driver(self, engine: StorageEngine, settings: Settings, result: LatencyResult) -> None:
        m, s = mean_std(result.latencies_ms)
        _append(self.data_dir / f"{engine.driver_csv_stem}.csv", _DRIVER_SUMMARY_FIELDS, {
            "timestamp": _now(), "engine": engine.engine_label, "profile": settings.profile_slug,
            "query_id": result.meta.get("query_id", engine.driver_query_id),
            "mean_latency_ms": round(m, 6), "std_latency_ms": round(s, 6),
            "n_runs": len(result.latencies_ms),
        })
