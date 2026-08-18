# Carbon-Aware Storage for Image-Based Time-Series — reproduction guide

**Artifact version 2.0.** This is the reproducibility artifact accompanying **"Carbon Footprint
and Carbon-Aware Selection of Document-Oriented, Relational, and Hybrid Object-Relational Storage
for Image-Based Time-Series Workloads in Green IoT"** (target journal: *Environment Systems and
Decisions*): the benchmark **code**, the measured **data**, the generated **figures**, the
**paper** sources, and — new in this version — the **recorder** and the **corpus of real camera
frames** used for the real-case validation.

It benchmarks three storage architectures across eight image resolutions (360p–6K), measuring
insertion, retrieval, storage amplification, and **directly measured per-resolution carbon**
(CodeCarbon + Intel RAPL), and converts the result into a carbon-aware decision framework.

### What changed since version 1.0

Version 1.0 contained the controlled single-image collage study only. Version 2.0 adds:

- **A second host.** The entire collage sweep repeated on a smaller machine (`data_collage_i7/`),
  including the memory exhaustion that makes MongoDB unrunnable there from 4K upward.
- **A real-case corpus.** 8,724 frames recorded from three cameras of an operational
  face-recognition-based attendance system, and the benchmark re-run over them so that every
  stored row holds a *different* photograph (`data_frames_*/`, `data_fleet/`).
- **The recorder** that produced the corpus (`code_realcase/`).
- **Four figures** covering the two-corpus and two-host comparisons, and a generator for them
  (`code/report_realcase.py`).

---

## Download and unpack

This record is split so that reviewers who only want to check the analysis need not download a
gigabyte of photographs. Each archive unpacks into the **same** directory tree, so extracting
them on top of one another reconstitutes the full working set.

| File | Size | Contents |
|---|---|---|
| `artifact-v2.0.zip` | ~10 MB | code, all measured data, figures, paper source. **Start here.** |
| `frames-networked-v2.0.zip` | ~450 MB | 2,845 frames, networked camera (H.264/RTSP, 1920×1080) |
| `frames-usb-external-v2.0.zip` | ~455 MB | 2,988 frames, external USB camera (MJPG, 1920×1080) |
| `frames-usb-builtin-v2.0.zip` | ~190 MB | 2,891 frames, built-in USB camera (MJPG, 1280×720) |

```bash
unzip artifact-v2.0.zip            # code/ code_realcase/ data*/ figures/ paper/
unzip 'frames-*-v2.0.zip'          # only if you want to re-run the real-case benchmark
```

The frame archives are needed **only** to regenerate the real-case measurements from scratch.
Every number and figure in the paper can be rebuilt from `artifact-v2.0.zip` alone, because the
per-run CSVs it contains are the measurements themselves.

All commands below run from inside the unpacked folder.

## Layout

```
.
├── README.md              # this file
├── code/                  # benchmark harness + figure generators + docker-compose
├── code_realcase/         # the camera recorder that produced the real corpus
├── data/                  # controlled collage sweep, larger host (i9)   [paper's primary data]
├── data_collage_i7/       # the same collage sweep, smaller host (i7)
├── data_frames_tapo/      # real frames, networked camera
├── data_frames_webcam2/   # real frames, external USB camera
├── data_frames_webcam1/   # real frames, built-in USB camera
├── data_fleet/            # mixed round-robin arm across all three cameras
├── figures/               # ten figures, PDF                             (generated)
└── paper/                 # main.tex, references.bib, sn-jnl.cls, figures/
```

---

## The software (`code/`)

One object-oriented harness drives all three architectures through the same measurement
protocol. Design: **Strategy** (each engine is a `StorageEngine` subclass owning its schema and
queries) + **Template Method** (the shared insert / retrieve / point-read / driver protocol lives
once in `engine_base.py` and calls small engine-specific primitives).

| File | Role |
|---|---|
| `run.py` | Single entry point: CLI, **auto-venv** bootstrap, Docker orchestration, timing/ETA, and the **retry-then-skip** failover. |
| `run_realcase.sh` | Runs the benchmark against the recorded frames, one camera at a time, each writing to its own data folder. |
| `engine_base.py` | `StorageEngine` abstract base — the shared measurement protocol. |
| `engine_postgres.py` | **Postgre** — PostgreSQL 15 / TimescaleDB, image inline in a `BYTEA` column (TOAST). |
| `engine_mongodb.py` | **Mongo** — MongoDB 7 native Time-Series Collection, image inline as BSON `BinData`. |
| `engine_postgres_minio.py` | **PostMin** — PostgreSQL metadata + image externalised to MinIO object storage. |
| `payloads.py` | Payload sources: the deterministic collage, a sequence of recorded frames, and a round-robin mix across cameras. |
| `carbon.py` | `CarbonTracker` — wraps each *(engine × operation × resolution)* measurement cell in a CodeCarbon run → `emissions.csv`. |
| `results.py` | CSV writers for every dimension (+ the skip log). |
| `config.py` | Workload profiles (360p…6K), payload source selection, settings, and output paths. |
| `report.py` | Aggregates a data folder into `threeway_summary.csv` and renders the six original figures. |
| `report_realcase.py` | Renders the four figures added by the revision, which compare two corpora or two hosts. |
| `docker-compose.yml` | `timescaledb` + `minio` + `mongodb`; only the services a phase needs are started, in isolation, for fair energy attribution. |
| `setup_rapl.sh` | One-time `sudo` helper to make Intel RAPL energy counters readable. |
| `assets/Schwarzsee.jpg` | Source image for the collage — see *Note on the source image filename* below. |
| `tests/` | Unit tests (config, payloads, CSV writer, measurement protocol, skip logic) — no databases required. |

Four operations are measured per *(engine, resolution)*: **insertion** throughput + storage
amplification, **bulk retrieval** (read back all 2,000 images in a time range), **latest-frame
read** (fetch the single most recent image), and **driver** round-trip overhead.

**Measurement boundary.** Each CodeCarbon tracker encloses an operation's *entire* measurement
cell: the untimed warm-up, the database reset before each repetition, the five repetitions, and
the storage-size and row-count queries between them. Dividing by the repetition count therefore
gives an **amortised per-run cost**, not the energy of an isolated operation against a warm
database. The paper reports it under that name. Note also that the insertion *timer* stops before
the transaction commits, while the tracker continues through it, so throughput and carbon do not
share a boundary and are not used to explain one another.

## The recorder (`code_realcase/`)

A small Tkinter application that displays one networked and two USB cameras, and records a
timed session from all three simultaneously. It is the tool that produced the real corpus.

Run `bash download_models.sh` first to fetch the OpenCV Zoo face models (38 MB, not shipped),
then `python3 launcher.py`. Copy `.env.example` to `.env` and fill in your own camera details;
no credentials are included in this artifact. See `code_realcase/README.md` for the full guide.

---

## The data

All CSVs are generated by `run.py`. `<engine>` ∈ `{postgres, mongo, postgres_minio}`,
`<res>` ∈ `{360p, 480p, 720p, 1080p, 1440p, 4k, 5k, 6k}`.

| File pattern | Contents |
|---|---|
| `results_<engine>_insert_runs_<res>.csv` / `_summary_<res>.csv` | Per-run and summary **insertion** metrics: rows/s, durations, on-disk sizes, and **storage amplification** (on-disk ÷ raw payload). |
| `results_<engine>_retrieve_runs_<res>.csv` / `_summary_<res>.csv` | **Bulk-retrieval** latency (ms) for materialising all 2,000 payloads in a time range. |
| `results_<engine>_point_read_runs_<res>.csv` / `_summary_<res>.csv` | **Latest-frame read** latency (ms). |
| `results_<engine>_driver_summary.csv` | Minimal client–server round-trip overhead (ms). |
| `emissions.csv` | CodeCarbon output, one row per `project_name = <engine>_<operation>_<resolution>`: `duration`, `energy_consumed` (kWh), `cpu_energy`, `ram_energy`, `emissions` (kg CO₂eq), grid intensity, host info. |
| `threeway_summary.csv` | The aggregated headline table (one row per resolution). Built by `report.py`. |
| `skipped.csv` | Cells attempted and abandoned (engine, resolution, attempts, error). |

**Two skipped cells, for two different reasons.** `data/skipped.csv` records **MongoDB at 6K**,
where time-series bucketing pushes a bucket document past the hard 16 MiB BSON limit (error
10334). `data_collage_i7/skipped.csv` records **MongoDB at 4K on the smaller host**, where the
kernel's out-of-memory killer terminated `mongod`. PostgreSQL and the hybrid completed every
resolution on both machines.

> **A failed cell still leaves a partial row in `emissions.csv`**, covering whatever work
> happened before the error. Anything reading the emissions log must exclude the cells listed in
> `skipped.csv` first, or MongoDB's 6K point appears merely cheap when it is in fact infeasible.
> `report_realcase.py` does this; if you write your own analysis, do the same.

### Payload size, not resolution

The `payload_size_mb` column of each insert summary is the decision variable the paper's
framework keys on. It differs by 3–5× between the collage and real camera output *at the same
resolution*, which is why both corpora are shipped.

---

## Figures

| Figure | Built by | Shows |
|---|---|---|
| `insert_throughput`, `retrieval_latency`, `point_read_latency`, `storage_amplification`, `carbon_per_resolution`, `carbon_breakdown` | `code/report.py` | The controlled collage sweep. |
| `realframes_carbon` | `code/report_realcase.py` | Identical rows beside distinct real frames, same host. |
| `crossover_collage`, `crossover_realcase` | `code/report_realcase.py` | Where the ingestion crossover falls under each corpus. |
| `applied_annual` | `code/report_realcase.py` | The framework applied to one camera for a year. |

---

## 1. Prerequisites

- **Docker** + **Docker Compose** (runs the three databases).
- **Python 3.11+** — `run.py` creates a local `.venv` and installs `requirements.txt` on first launch (set `IOTBENCH_NO_VENV=1` to use the current interpreter).
- **TeX Live** with `latexmk` + `bibtex` (to build the paper). `sn-jnl.cls`/`sn-*.bst` are bundled in `paper/`.
- *(Optional)* **Intel RAPL** for true hardware energy; otherwise CodeCarbon falls back to TDP estimates.

## 2. Rebuild the figures and tables from the shipped measurements

No benchmark run and no Docker needed — the `data*/` folders already hold the measurements:

```bash
cd code
python report.py                 # six original figures + data/threeway_summary.csv
python report_realcase.py        # the four figures added by the revision
```

## 3. Regenerate the measurements from scratch

This **overwrites** the shipped CSVs, so copy them aside first if you want to compare.

```bash
cd code
bash setup_rapl.sh               # one-time: make RAPL counters readable (self-elevates)

python run.py --report           # the controlled collage sweep, 360p -> 6K
bash run_realcase.sh --dry-run   # show the real-case plan without running it
bash run_realcase.sh             # the real-case sweep (needs the frame archives unpacked)
```

Useful variants:

```bash
python run.py 1080p 4k 6k             # only these resolutions
python run.py 4k --engines mongodb    # one resolution, one engine
python run.py --no-docker 4k          # services already running
python run.py --dry-run               # print the plan and exit
```

Run the tests (no databases needed):

```bash
cd code && python -m unittest discover -s tests
```

## 4. Build the paper

```bash
cd paper
latexmk -pdf -interaction=nonstopmode main.tex   # pdflatex + bibtex -> main.pdf
latexmk -c                                        # remove aux files, keep main.pdf
```

Figures are read from `figures/`; the bibliography is `references.bib`. The Springer class and
bibliography style are bundled, so no extra package install is needed.

---

## Notes

### Note on the source image filename

The collage payload is built from `code/assets/Schwarzsee.jpg`. **The filename is historical and
does not describe the image.** The file is a freely-licensed photograph of **Durdle Door, Dorset,
UK** by JJ Perks via [Pexels](https://www.pexels.com/photo/bay-with-orange-seashore-under-white-and-gray-clouds-8567869/),
resized to 6144×3456, and that is what the paper cites. The name was retained so that the file
hash matches the one used to generate the shipped CSVs; renaming it would silently change the
payloads and invalidate the comparison.

### Anonymisation

This artifact accompanies a double-anonymous submission and has been prepared accordingly.
CodeCarbon records the measuring machine's latitude, longitude, and administrative region in
every `emissions.csv`; **those three columns are blanked** in the published copies. The country
is retained, because the paper's grid-intensity factor depends on it. Camera credentials
(`.env`), virtual environments, the downloaded face models, and any enrolled face photographs
are excluded entirely. Recorded frames carry no EXIF metadata.

### Ethics and the recorded corpus

The corpus was recorded specifically for this study. No recognition function was invoked and no
enrolled identity or template was accessed; the cameras were read directly and only the resulting
image files were used, as binary payloads. Recording was carried out with no other person
present, and no biometric template was computed or stored. Every saved frame was then passed
through a face detector (YuNet, confidence threshold 0.35) and none produced a detection. That is
evidence the corpus contains **no detectable faces** — it is not a proof that it contains no
personal data, which a detector sweep cannot establish.

### Configuration

Workload size, payload source, and ports are environment-variable configurable
(`BENCHMARK_TOTAL_ROWS`, `BENCHMARK_BATCH_SIZE`, `BENCHMARK_INSERT_RUNS`,
`BENCHMARK_PAYLOAD_SOURCE`, `BENCHMARK_FRAMES_DIR`, `BENCHMARK_DATA_DIR`, `POSTGRES_PORT`,
`MONGO_URI`, `MINIO_ENDPOINT`, …) — see [`code/README.md`](code/README.md). The exact environment
(CPU, OS, database and library versions) used for the reported numbers is documented in the
paper's environment tables, one per host.

---

## Citation

If you use this artifact or its data, please cite the accompanying paper:

> [Authors hidden for double-anonymous review], *Carbon Footprint and Carbon-Aware Selection of
> Document-Oriented, Relational, and Hybrid Object-Relational Storage for Image-Based
> Time-Series Workloads in Green IoT*, Environment Systems and Decisions (under review).
