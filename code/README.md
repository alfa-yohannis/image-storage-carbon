# Code — Environment Systems and Decisions: unified three-way benchmark (object-oriented)

One object-oriented harness that evaluates all three storage architectures across every
dimension both source papers measured, over the full **360p → 6K** sweep. Everything runs
through a single Python entry point — **`run.py`** — with parameters. Outputs are written
**outside** this folder:

- data (CSVs + `emissions.csv`) → [`../data/`](../data)
- figures (PDFs) → [`../figures/`](../figures)

## Quick start

```bash
python run.py                      # full 360p->6K sweep, all engines
python run.py 360p                 # only 360p, all engines
python run.py 360p --report        # 360p, all engines, then build the report + figures
python run.py 360p 4k 6k           # several specific resolutions
python run.py 1080p --engines mongodb        # one resolution, one engine
python run.py --dry-run 4k 5k                # print the plan and exit
python run.py --no-docker 4k                 # services already running
```

On **first launch** `run.py` automatically creates a local `.venv/`, installs
`requirements.txt`, and re-executes itself inside it — no manual setup. Set
`IOTBENCH_NO_VENV=1` to use the current interpreter instead. From another folder, just use
the full path: `python /abs/path/to/code/run.py 360p --report`.

## Energy measurement (RAPL)

CodeCarbon reads Intel RAPL counters for real CPU/RAM energy; those sysfs files are
root-only by default. Grant read access **once** (this also installs a systemd unit so it
survives reboots):

```bash
bash setup_rapl.sh        # self-elevates with sudo
```

If RAPL stays unreadable, `run.py` warns at startup and CodeCarbon falls back to TDP
estimates; pass `--no-carbon` to skip energy tracking. This privileged step can't run from
the unprivileged Python process, so it lives in this one small helper.

## Progress / duration

`run.py` prints live progress: a `[done/total]` counter, the payload size, per-step
durations (driver / insert / retrieval / point-read), per-resolution and per-phase
elapsed, a running total, and an ETA — e.g.:

```
==== [1/8] postgres :: 360p  (0.09 MB/sample) ====
   - insert ... 
   - insert done in 00:00:42
   [1/8] postgres:360p done in 00:00:51  |  elapsed 00:01:10  |  ETA 00:08:10
```

## Layout

```
code/
├── run.py                  # single entry point (CLI + auto-venv + orchestration + timing)
├── report.py               # three-way aggregator -> data/threeway_summary.csv + figures/
├── config.py               # WorkloadProfile, Settings, Locations (data/ & figures/ paths)
├── payloads.py             # MediaPayload + PayloadFactory
├── carbon.py               # CarbonTracker (CodeCarbon context manager)
├── results.py              # ResultWriter (CSV)
├── engine_base.py          # StorageEngine ABC — shared measurement protocol
├── engine_postgres.py      # PostgreSQL / TimescaleDB (inline BYTEA)
├── engine_postgres_minio.py# PostgreSQL metadata + MinIO object payloads
├── engine_mongodb.py       # MongoDB time-series (inline BSON)
├── docker-compose.yml      # timescaledb + minio + mongodb (project-scoped)
├── requirements.txt        # Python dependencies (auto-installed into .venv)
├── setup_rapl.sh           # one-time (sudo): make Intel RAPL readable for CodeCarbon
├── assets/                 # source image for payload generation
└── tests/                  # unit-test suite
```

## Design

- **Strategy** — each engine is a `StorageEngine` subclass encapsulating its own schema,
  queries, and storage-size accounting.
- **Template Method** — `StorageEngine.run_insert/run_retrieval/run_point_read/run_driver`
  implement the shared protocol (warm-up, run counts, timing, aggregation) once and call
  small engine-specific primitives (`_reset`, `_insert_rows`, `_retrieval_once`, …).
- **Separation of concerns** — measurement (engines) vs. persistence (`ResultWriter`) vs.
  energy (`CarbonTracker`) vs. orchestration (`run.py`).

## Resolutions

Short names: **`360p 480p 720p 1080p 1440p 4k 5k 6k`** (plus `video_1080p`). Supply one or
more as positional arguments; omit them for the full sweep. Names are case-insensitive, and
the old long keys (`6k_uhd_image`, `360p_sd_image`, …) still resolve.

## Engines (`--engines`, comma-separated; default all)

| Tag | Architecture | Binary payload | Services |
|---|---|---|---|
| `postgres` | PostgreSQL 15 / TimescaleDB | inline `BYTEA` (TOAST) | timescaledb |
| `postgres_minio` | PostgreSQL + MinIO | externalised object (HTTP) | timescaledb + minio |
| `mongodb` | MongoDB 7 Time-Series Collection | inline BSON `BinData` | mongodb |

## Dimensions (per engine × per resolution)

| Dimension | Method | CSV stem |
|---|---|---|
| Insert throughput **+ storage amplification** | `run_insert` | `results_<engine>_insert_{runs,summary}` |
| Full-materialisation retrieval latency | `run_retrieval` | `results_<engine>_retrieve_{runs,summary}` |
| Latest-payload point-read latency | `run_point_read` | `results_<engine>_point_read_{runs,summary}` |
| Driver / roundtrip overhead | `run_driver` | `results_<engine>_driver_summary` |
| Energy / CO₂ (CodeCarbon, RAPL) | `CarbonTracker` | `emissions.csv` (`<engine>_<dim>_<profile>`) |

Per-resolution carbon is measured **directly** (one tracker per engine/dimension/resolution),
not estimated. Filenames are namespaced, e.g. `results_mongo_insert_summary_4k.csv`.

## CLI flags

`[resolutions ...]` · `--engines a,b,c` · `--no-docker` · `--no-carbon` · `--report` · `--dry-run`

Each engine phase brings up only the services it needs (isolation for fair carbon), wipes
the DB volume between phases, and tears down afterwards. The compose project is named
`iot-image-tsdb-unified` and containers are auto-named, so it won't clash with other stacks.

## Tests

```bash
python -m unittest discover -s tests        # use .venv/bin/python if deps aren't in your base env
```
Covers config / resolution resolution, payload generation, the CSV writer, and the
measurement protocol (in-memory fake engine) — **no databases required**. Engine-contract
tests run only when the DB drivers are installed.

## Configuration (env vars)

`MEDIA_PROFILE`, `BENCHMARK_TOTAL_ROWS` (2000), `BENCHMARK_BATCH_SIZE` (50),
`BENCHMARK_INSERT_RUNS` (5), `BENCHMARK_AGG_RUNS` (5), `BENCHMARK_POINT_READ_RUNS` (5),
`POSTGRES_PORT` (55432), `MONGO_URI`, `MINIO_ENDPOINT` (127.0.0.1:59000),
`BENCHMARK_DATA_DIR`, `BENCHMARK_FIGURES_DIR`, `IOTBENCH_NO_VENV`. See `config.py`.

## Provenance

Merged and refactored from the two original conference-paper codebases at the repo root
(which keep their original result CSVs):
[PG vs MongoDB](../../postgre-vs-mongodb-carbon-footprint/code) ·
[PG vs PG+MinIO](../../postgre-vs-postgre-minio-carbon-footprint/code).
The MongoDB arm uses the **inline-BSON** design (paper-3); paper-4's MongoDB+MinIO hybrid is
intentionally not used. See the roadmap in [`../README.md`](../README.md).
