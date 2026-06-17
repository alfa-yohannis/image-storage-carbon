"""PostgreSQL / TimescaleDB engine with inline BYTEA payloads."""
from __future__ import annotations

import time
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import execute_batch

from engine_base import StorageEngine, StorageSizes
from payloads import MediaPayload

_DDL = """
CREATE EXTENSION IF NOT EXISTS timescaledb;
CREATE TABLE IF NOT EXISTS {table} (
    sample_id BIGSERIAL NOT NULL,
    device_id BIGINT NOT NULL,
    ts TIMESTAMPTZ NOT NULL,
    profile_name TEXT NOT NULL,
    payload_kind TEXT NOT NULL,
    payload_data BYTEA NOT NULL,
    payload_size_bytes INTEGER NOT NULL,
    width INTEGER, height INTEGER, mime_type TEXT NOT NULL, codec TEXT,
    duration_ms INTEGER NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (ts, sample_id)
);
SELECT create_hypertable('{table}', by_range('ts'), if_not_exists => TRUE, create_default_indexes => FALSE);
CREATE INDEX IF NOT EXISTS idx_{table}_device_ts_desc ON {table} (device_id, ts DESC);
"""

_INSERT_SQL = """
INSERT INTO {table} (device_id, ts, profile_name, payload_kind, payload_data,
    payload_size_bytes, width, height, mime_type, codec, duration_ms)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
"""


class PostgresEngine(StorageEngine):
    name = "postgres"
    engine_label = "postgresql+timescaledb"
    csv_prefix = "results_postgres"
    driver_csv_stem = "results_postgres_driver_summary"
    driver_query_id = "Q_driver_roundtrip_select_1"
    services = ("timescaledb",)

    def __init__(self, settings):
        super().__init__(settings)
        self.table = settings.postgres_table_name
        self._ret_conn = None
        self._pr_conn = None
        self._pr_cur = None
        self._drv_conn = None
        self._drv_cur = None

    # ---- helpers -------------------------------------------------------- #
    def _connect(self, autocommit: bool):
        conn = psycopg2.connect(**self.settings.postgres_config)
        conn.autocommit = autocommit
        return conn

    def wait_ready(self, timeout_sec: int = 90) -> None:
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            try:
                self._connect(True).close()
                return
            except psycopg2.Error:
                time.sleep(1)
        raise TimeoutError("Timed out waiting for PostgreSQL.")

    # ---- insert primitives ---------------------------------------------- #
    def _reset(self) -> None:
        conn = self._connect(True)
        try:
            with conn.cursor() as cur:
                cur.execute(f"DROP TABLE IF EXISTS {self.table} CASCADE;")
                cur.execute(_DDL.format(table=self.table))
        finally:
            conn.close()

    def _insert_rows(self, payload: MediaPayload, n_rows: int, batch_size: int) -> tuple[int, float]:
        sql = _INSERT_SQL.format(table=self.table)
        conn = self._connect(False)
        inserted = 0
        try:
            with conn.cursor() as cur:
                t0 = time.perf_counter()
                batch = []
                while inserted < n_rows:
                    ts = datetime.now(timezone.utc)
                    batch.append((self.settings.device_id, ts, payload.profile_name, payload.payload_kind,
                                  psycopg2.Binary(payload.payload_bytes), payload.payload_size_bytes,
                                  payload.width, payload.height, payload.mime_type, payload.codec,
                                  payload.duration_ms))
                    if len(batch) >= batch_size:
                        execute_batch(cur, sql, batch)
                        inserted += len(batch)
                        batch.clear()
                if batch:
                    execute_batch(cur, sql, batch)
                    inserted += len(batch)
                duration = time.perf_counter() - t0  # excludes commit, as in the original
            conn.commit()
        finally:
            conn.close()
        return inserted, duration

    def _storage_sizes(self) -> StorageSizes:
        conn = self._connect(True)
        try:
            with conn.cursor() as cur:
                try:
                    cur.execute(f"""
                        SELECT COALESCE(table_bytes,0), COALESCE(index_bytes,0),
                               COALESCE(toast_bytes,0), COALESCE(total_bytes,0)
                        FROM hypertable_detailed_size('{self.table}');""")
                    table_bytes, index_bytes, toast_bytes, total_bytes = cur.fetchone()
                    table_data_bytes = table_bytes + toast_bytes
                    table_total_bytes = total_bytes
                except psycopg2.Error:
                    conn.rollback()
                    cur.execute(f"""
                        SELECT COALESCE(pg_total_relation_size('{self.table}'),0),
                               COALESCE(pg_relation_size('{self.table}'),0),
                               COALESCE(pg_indexes_size('{self.table}'),0)""")
                    table_total_bytes, table_data_bytes, index_bytes = cur.fetchone()
                cur.execute("SELECT pg_database_size(current_database());")
                (db_bytes,) = cur.fetchone()
        finally:
            conn.close()
        return StorageSizes(int(table_total_bytes), int(table_data_bytes), int(index_bytes), int(db_bytes))

    def _row_count(self) -> int:
        conn = self._connect(True)
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {self.table};")
                (count,) = cur.fetchone()
        finally:
            conn.close()
        return int(count)

    # ---- retrieval (full time-range materialisation) -------------------- #
    def _retrieval_prepare(self) -> bool:
        self._ret_conn = self._connect(False)
        with self._ret_conn.cursor() as cur:
            cur.execute(f"SELECT MIN(ts), MAX(ts) FROM {self.table} WHERE device_id = %s;",
                        (self.settings.device_id,))
            self._ts_min, self._ts_max = cur.fetchone()
        if self._ts_min is None:
            self._retrieval_finish()
            return False
        return True

    def _retrieval_once(self) -> tuple[int, int]:
        query = f"""SELECT ts, payload_data FROM {self.table}
                    WHERE device_id = %s AND ts >= %s AND ts <= %s ORDER BY ts;"""
        byte_sum = count = 0
        with self._ret_conn.cursor(name="retrieve_pg") as named:
            named.itersize = 20
            named.execute(query, (self.settings.device_id, self._ts_min, self._ts_max))
            for _, payload_data in named:
                byte_sum += len(payload_data)
                count += 1
        return count, byte_sum

    def _retrieval_finish(self) -> None:
        if self._ret_conn is not None:
            self._ret_conn.close()
            self._ret_conn = None

    # ---- point read ----------------------------------------------------- #
    def _point_read_prepare(self) -> None:
        self._pr_conn = self._connect(False)
        self._pr_cur = self._pr_conn.cursor()
        self._pr_query = f"""SELECT ts, payload_data, payload_size_bytes, mime_type
                             FROM {self.table} WHERE device_id = %s ORDER BY ts DESC LIMIT %s;"""

    def _point_read_once(self) -> None:
        self._pr_cur.execute(self._pr_query, (self.settings.device_id, self.settings.point_read_limit))
        rows = self._pr_cur.fetchall()
        if rows:
            len(rows[0][1])

    def _point_read_finish(self) -> None:
        if self._pr_cur is not None:
            self._pr_cur.close()
        if self._pr_conn is not None:
            self._pr_conn.close()
        self._pr_cur = self._pr_conn = None

    # ---- driver overhead ------------------------------------------------ #
    def _driver_prepare(self) -> None:
        self._drv_conn = self._connect(False)
        self._drv_cur = self._drv_conn.cursor()

    def _driver_once(self) -> None:
        self._drv_cur.execute("SELECT 1;")
        self._drv_cur.fetchone()

    def _driver_finish(self) -> None:
        if self._drv_cur is not None:
            self._drv_cur.close()
        if self._drv_conn is not None:
            self._drv_conn.close()
        self._drv_cur = self._drv_conn = None
