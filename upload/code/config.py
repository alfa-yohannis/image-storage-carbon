"""Configuration: workload profiles, filesystem locations, and run settings.

Outputs are routed to the ESD folder, not the code folder:
    data    -> 01_environment_systems_and_decisions/data
    figures -> 01_environment_systems_and_decisions/figures
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    return int(raw) if raw is not None else default


# --------------------------------------------------------------------------- #
# Workload profiles
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class WorkloadProfile:
    name: str
    payload_kind: str
    width: int
    height: int
    mime_type: str = "image/jpeg"
    codec: str = "jpeg"
    image_quality: int | None = 90
    video_duration_sec: float | None = None
    video_fps: int | None = None
    video_crf: int | None = None
    warmup_rows: int = 100
    total_rows: int = 2000
    batch_size: int = 50
    insert_runs: int = 5
    description: str = ""


def _img(name: str, w: int, h: int, desc: str) -> WorkloadProfile:
    return WorkloadProfile(name=name, payload_kind="image", width=w, height=h, description=desc)


WORKLOAD_PROFILES: dict[str, WorkloadProfile] = {
    "360p": _img("360p", 640, 360, "360p SD still-image workload."),
    "480p": _img("480p", 854, 480, "480p SD still-image workload."),
    "720p": _img("720p", 1280, 720, "720p HD still-image workload."),
    "1080p": _img("1080p", 1920, 1080, "1080p Full-HD still-image workload."),
    "1440p": _img("1440p", 2560, 1440, "1440p QHD still-image workload."),
    "4k": _img("4k", 3840, 2160, "4K UHD still-image workload."),
    "5k": _img("5k", 5120, 2880, "5K still-image workload."),
    "6k": _img("6k", 6144, 3456, "6K still-image workload (largest payload)."),
    "video_1080p": WorkloadProfile(
        name="video_1080p", payload_kind="video", width=1920, height=1080,
        mime_type="video/mp4", codec="h264", image_quality=None,
        video_duration_sec=3.0, video_fps=24, video_crf=23,
        description="1080p H.264 clip workload generated from the source image.",
    ),
}

# Accept the older long keys (e.g. "6k_uhd_image") and paper-3/4 keys as aliases.
PROFILE_ALIASES: dict[str, str] = {
    "360p_sd_image": "360p", "360p_image": "360p", "360_sd_image": "360p",
    "480p_sd_image": "480p", "480_sd_image": "480p",
    "720p_hd_image": "720p", "720_hd_image": "720p",
    "1080p_fhd_image": "1080p", "1080_fhd_image": "1080p", "large_fhd_image": "1080p",
    "1440p_qhd_image": "1440p", "1440_qhd_image": "1440p",
    "4k_uhd_image": "4k", "4k_uhd": "4k",
    "5k_uhd_image": "5k", "5k_uhd": "5k", "5k_image": "5k",
    "6k_uhd_image": "6k", "6k_uhd": "6k", "6k_image": "6k",
    "fhd_video_clip": "video_1080p",
}

# Canonical 360p -> 6K sweep used by the runner.
DEFAULT_SWEEP: list[str] = ["360p", "480p", "720p", "1080p", "1440p", "4k", "5k", "6k"]


def resolve_profile(name: str) -> WorkloadProfile:
    """Resolve a profile key, short resolution name (e.g. '4k'), or legacy alias.
    Matching is case-insensitive for aliases."""
    for candidate in (name, name.lower()):
        if candidate in WORKLOAD_PROFILES:
            return WORKLOAD_PROFILES[candidate]
        if candidate in PROFILE_ALIASES:
            return WORKLOAD_PROFILES[PROFILE_ALIASES[candidate]]
    raise ValueError(
        f"Unknown resolution/profile '{name}'. "
        f"Available: {', '.join(WORKLOAD_PROFILES)} "
        f"(legacy aliases like 6k_uhd_image are also accepted)."
    )


# --------------------------------------------------------------------------- #
# Filesystem locations  (code/ -> ESD root -> data/ , figures/)
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Locations:
    code_dir: Path
    esd_root: Path
    data_dir: Path
    figures_dir: Path
    assets_dir: Path
    source_image_path: Path

    @classmethod
    def create(cls) -> "Locations":
        code_dir = Path(__file__).resolve().parent          # 01_*/code
        esd_root = code_dir.parent                            # 01_*/
        data_dir = Path(os.getenv("BENCHMARK_DATA_DIR", str(esd_root / "data")))
        figures_dir = Path(os.getenv("BENCHMARK_FIGURES_DIR", str(esd_root / "figures")))
        assets_dir = code_dir / "assets"
        source_image = Path(
            os.getenv("BENCHMARK_SOURCE_IMAGE", str(assets_dir / "Schwarzsee.jpg"))
        ).resolve()
        data_dir.mkdir(parents=True, exist_ok=True)
        figures_dir.mkdir(parents=True, exist_ok=True)
        return cls(code_dir, esd_root, data_dir, figures_dir, assets_dir, source_image)


# --------------------------------------------------------------------------- #
# Settings
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Settings:
    workload: WorkloadProfile
    locations: Locations
    device_id: int
    postgres_config: dict[str, object]
    mongo_uri: str
    mongo_db_name: str
    mongo_collection_name: str
    postgres_table_name: str
    postgres_minio_table_name: str
    minio_endpoint: str
    minio_access_key: str
    minio_secret_key: str
    minio_bucket: str
    minio_secure: bool
    warmup_rows: int
    total_rows: int
    batch_size: int
    insert_runs: int
    aggregation_warmup_runs: int
    aggregation_runs: int
    driver_warmup_runs: int
    driver_runs: int
    point_read_warmup_runs: int
    point_read_runs: int
    point_read_limit: int

    @property
    def profile_slug(self) -> str:
        return self.workload.name

    @property
    def data_dir(self) -> Path:
        return self.locations.data_dir

    @property
    def workload_label(self) -> str:
        w = self.workload
        if w.payload_kind == "image":
            return f"{w.width}x{w.height} JPEG"
        return f"{w.width}x{w.height} {w.codec.upper()} {w.video_duration_sec or 0:.1f}s/{w.video_fps or 0}fps"

    def with_profile(self, profile_name: str) -> "Settings":
        wl = resolve_profile(profile_name)
        return replace(
            self,
            workload=wl,
            warmup_rows=_env_int("BENCHMARK_WARMUP_ROWS", wl.warmup_rows),
            total_rows=_env_int("BENCHMARK_TOTAL_ROWS", wl.total_rows),
            batch_size=_env_int("BENCHMARK_BATCH_SIZE", wl.batch_size),
            insert_runs=_env_int("BENCHMARK_INSERT_RUNS", wl.insert_runs),
        )

    @classmethod
    def load(cls, profile_name: str | None = None) -> "Settings":
        locations = Locations.create()
        wl = resolve_profile(profile_name or os.getenv("MEDIA_PROFILE", "1080p"))
        postgres_config = {
            "dbname": os.getenv("POSTGRES_DB", "iot_ts"),
            "user": os.getenv("POSTGRES_USER", "postgres"),
            "password": os.getenv("POSTGRES_PASSWORD", "postgres"),
            "host": os.getenv("POSTGRES_HOST", "127.0.0.1"),
            "port": _env_int("POSTGRES_PORT", 55432),
        }
        return cls(
            workload=wl,
            locations=locations,
            device_id=_env_int("DEVICE_ID", 1),
            postgres_config=postgres_config,
            mongo_uri=os.getenv("MONGO_URI", "mongodb://mongo:mongo@127.0.0.1:57017/?authSource=admin"),
            mongo_db_name=os.getenv("MONGO_DB", "iot_ts"),
            mongo_collection_name=os.getenv("MONGO_COLLECTION", "sensor_media"),
            postgres_table_name=os.getenv("POSTGRES_TABLE", "sensor_media"),
            postgres_minio_table_name=os.getenv("POSTGRES_MINIO_TABLE", "sensor_media_minio"),
            minio_endpoint=os.getenv("MINIO_ENDPOINT", "127.0.0.1:59000"),
            minio_access_key=os.getenv("MINIO_ACCESS_KEY", "minioadmin"),
            minio_secret_key=os.getenv("MINIO_SECRET_KEY", "minioadmin"),
            minio_bucket=os.getenv("MINIO_BUCKET", "sensor-media"),
            minio_secure=os.getenv("MINIO_SECURE", "false").lower() == "true",
            warmup_rows=_env_int("BENCHMARK_WARMUP_ROWS", wl.warmup_rows),
            total_rows=_env_int("BENCHMARK_TOTAL_ROWS", wl.total_rows),
            batch_size=_env_int("BENCHMARK_BATCH_SIZE", wl.batch_size),
            insert_runs=_env_int("BENCHMARK_INSERT_RUNS", wl.insert_runs),
            aggregation_warmup_runs=_env_int("BENCHMARK_AGG_WARMUP_RUNS", 2),
            aggregation_runs=_env_int("BENCHMARK_AGG_RUNS", 5),
            driver_warmup_runs=_env_int("BENCHMARK_DRIVER_WARMUP_RUNS", 10),
            driver_runs=_env_int("BENCHMARK_DRIVER_RUNS", 10),
            point_read_warmup_runs=_env_int("BENCHMARK_POINT_READ_WARMUP_RUNS", 2),
            point_read_runs=_env_int("BENCHMARK_POINT_READ_RUNS", 5),
            point_read_limit=_env_int("BENCHMARK_POINT_READ_LIMIT", 1),
        )

    def describe(self) -> str:
        return (
            f"profile={self.profile_slug}, payload={self.workload_label}, "
            f"rows/run={self.total_rows}, batch={self.batch_size}, insert_runs={self.insert_runs}"
        )
