"""MongoDB native Time-Series Collection with inline BSON (BinData) payloads."""
from __future__ import annotations

import time
from datetime import datetime, timezone

from pymongo import MongoClient

from engine_base import StorageEngine, StorageSizes
from payloads import MediaPayload


class MongoEngine(StorageEngine):
    name = "mongodb"
    engine_label = "mongodb_timeseries"
    csv_prefix = "results_mongo"
    driver_csv_stem = "results_mongo_driver_summary"
    driver_query_id = "Q_driver_roundtrip_ping"
    services = ("mongodb",)

    def __init__(self, settings):
        super().__init__(settings)
        self._client = None
        self._ts_min = self._ts_max = None

    def _get_client(self) -> MongoClient:
        if self._client is None:
            self._client = MongoClient(self.settings.mongo_uri)
        return self._client

    def _collection(self):
        return self._get_client()[self.settings.mongo_db_name][self.settings.mongo_collection_name]

    def _db(self):
        return self._get_client()[self.settings.mongo_db_name]

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def wait_ready(self, timeout_sec: int = 90) -> None:
        deadline = time.time() + timeout_sec
        while time.time() < deadline:
            try:
                client = MongoClient(self.settings.mongo_uri, serverSelectionTimeoutMS=1500)
                client.admin.command({"ping": 1})
                client.close()
                return
            except Exception:
                time.sleep(1)
        raise TimeoutError("Timed out waiting for MongoDB.")

    # ---- insert primitives ---------------------------------------------- #
    def _reset(self) -> None:
        db = self._db()
        if self.settings.mongo_collection_name in db.list_collection_names():
            db.drop_collection(self.settings.mongo_collection_name)
        db.create_collection(
            self.settings.mongo_collection_name,
            timeseries={"timeField": "ts", "metaField": "meta", "granularity": "seconds"},
        )
        db[self.settings.mongo_collection_name].create_index(
            [("meta.device_id", 1), ("ts", -1)], name="idx_device_ts_desc")

    def _insert_rows(self, payload: MediaPayload, n_rows: int, batch_size: int) -> tuple[int, float]:
        coll = self._collection()
        inserted = 0
        t0 = time.perf_counter()
        batch = []
        while inserted < n_rows:
            batch.append({
                "meta": {"device_id": self.settings.device_id, "profile": payload.profile_name,
                         "payload_kind": payload.payload_kind},
                "ts": datetime.now(timezone.utc),
                "payload_data": payload.payload_bytes,
                "payload_size_bytes": payload.payload_size_bytes,
                "width": payload.width, "height": payload.height,
                "mime_type": payload.mime_type, "codec": payload.codec,
                "duration_ms": payload.duration_ms,
            })
            if len(batch) >= batch_size:
                try:
                    coll.insert_many(batch, ordered=False)
                except Exception as exc:
                    print(f"[mongo] batch insert failed: {type(exc).__name__}: {str(exc)[:100]}")
                inserted += len(batch)
                batch.clear()
        if batch:
            try:
                coll.insert_many(batch, ordered=False)
            except Exception as exc:
                print(f"[mongo] remainder insert failed: {type(exc).__name__}: {str(exc)[:100]}")
            inserted += len(batch)
        return inserted, time.perf_counter() - t0

    def _storage_sizes(self) -> StorageSizes:
        db = self._db()
        dbstats = db.command("dbStats")
        collstats = db.command("collStats", self.settings.mongo_collection_name)
        coll_storage = collstats.get("storageSize", collstats.get("size", 0))
        coll_index = collstats.get("totalIndexSize", 0)
        db_storage = dbstats.get("storageSize", dbstats.get("dataSize", 0))
        db_index = dbstats.get("indexSize", 0)
        return StorageSizes(int(coll_storage + coll_index), int(coll_storage),
                            int(coll_index), int(db_storage + db_index))

    def _row_count(self) -> int:
        return int(self._collection().count_documents({}))

    # ---- retrieval ------------------------------------------------------ #
    def _retrieval_prepare(self) -> bool:
        coll = self._collection()
        rng = list(coll.aggregate([
            {"$match": {"meta.device_id": self.settings.device_id}},
            {"$group": {"_id": None, "min_ts": {"$min": "$ts"}, "max_ts": {"$max": "$ts"}}},
        ]))
        if not rng:
            return False
        self._ts_min, self._ts_max = rng[0]["min_ts"], rng[0]["max_ts"]
        return True

    def _retrieval_once(self) -> tuple[int, int]:
        coll = self._collection()
        cursor = coll.find(
            {"meta.device_id": self.settings.device_id, "ts": {"$gte": self._ts_min, "$lte": self._ts_max}},
            {"ts": 1, "payload_data": 1, "_id": 0}, batch_size=20,
        ).sort("ts", 1)
        byte_sum = count = 0
        for doc in cursor:
            byte_sum += len(doc["payload_data"])
            count += 1
        return count, byte_sum

    # ---- point read ----------------------------------------------------- #
    def _point_read_once(self) -> None:
        doc = self._collection().find_one({"meta.device_id": self.settings.device_id}, sort=[("ts", -1)])
        if doc:
            len(doc["payload_data"])

    # ---- driver overhead ------------------------------------------------ #
    def _driver_once(self) -> None:
        self._get_client().admin.command({"ping": 1})
