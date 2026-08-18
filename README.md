# Carbon-Aware Storage for Image-Based Time-Series — reproduction guide

This folder contains everything needed to reproduce the study **"Carbon Footprint and
Carbon-Aware Selection of Document-Oriented, Relational, and Hybrid Object-Relational
Storage for Image-Based Time-Series Workloads in Green IoT"** (target journal:
*Environment Systems and Decisions*): the benchmark **code**, the measured **data**, the
generated **figures**, and the **paper** sources.

It benchmarks three storage architectures across eight image resolutions (360p–6K),
measuring insertion, retrieval, storage amplification, and **directly measured per-resolution
carbon** (CodeCarbon + Intel RAPL), and converts the result into a carbon-aware decision
framework. It is the reproducibility artifact accompanying the paper.

---

## Repository layout

```
.
├── README.md            # this file (how to reproduce + what the code/data are)
├── code/                # benchmark harness (Python) + docker-compose + tests
├── code_realcase/       # camera application that records the real-case corpus
├── data/                # measured CSVs, collage payload, i9 host   (generated)
├── data_frames_*/       # measured CSVs, real camera frames         (generated)
├── data_fleet/          # measured CSVs, mixed-camera round-robin   (generated)
├── data_collage_i7/     # measured CSVs, collage payload, i7 host   (generated)
├── figures/             # comparison figures, PDF                   (generated)
├── reviews/             # editor correspondence and response letter
├── declarations/        # ready-to-paste text for the submission form (not anonymised)
├── zenodo/              # make_artifact.py + the published archives  (generated)
└── paper/               # main.tex, references.bib, sn-jnl.cls      (the manuscript)
```

The study has two payload corpora, and the directory names record which produced which
results. The **collage** corpus builds one image per resolution and stores it in every
row; it is exactly reproducible, which is what a controlled comparison needs. The
**real-case** corpus is a set of independently captured camera frames, so every stored
row holds a different picture. Keeping them in separate directories means a run of one
can never overwrite the results of the other.

---

## The software (`code/`)

One object-oriented harness drives all three architectures through the same measurement
protocol. Design: **Strategy** (each engine is a `StorageEngine` subclass owning its schema
and queries) + **Template Method** (the shared insert / retrieve / point-read / driver
protocol lives once in `engine_base.py` and calls small engine-specific primitives).

| File | Role |
|---|---|
| `run.py` | Single entry point: CLI, **auto-venv** bootstrap, Docker orchestration, timing/ETA, and the **retry-then-skip** failover. |
| `engine_base.py` | `StorageEngine` abstract base — the shared measurement protocol. |
| `engine_postgres.py` | **Postgre** — PostgreSQL 15 / TimescaleDB, image inline in a `BYTEA` column (TOAST). |
| `engine_mongodb.py` | **Mongo** — MongoDB 7 native Time-Series Collection, image inline as BSON `BinData`. |
| `engine_postgres_minio.py` | **PostMin** — PostgreSQL metadata + image externalised to MinIO object storage. |
| `payloads.py` | Payload sources: the deterministic collage, a sequence of recorded frames, and a round-robin mix across cameras. |
| `run_realcase.sh` | Runs the sweep against recorded camera frames, one camera at a time, each writing to its own data folder. |
| `carbon.py` | `CarbonTracker` — wraps each *(engine × operation × resolution)* in a CodeCarbon run → `emissions.csv`. |
| `results.py` | CSV writers for every dimension (+ the skip log). |
| `config.py` | Workload profiles (360p…6K), payload-source selection, settings, and output paths. |
| `report.py` | Aggregates a data folder into `threeway_summary.csv` and renders the six sweep figures. |
| `report_realcase.py` | Renders the four figures that compare two corpora or two hosts. |
| `docker-compose.yml` | `timescaledb` + `minio` + `mongodb`; only the services a phase needs are started, in isolation, for fair energy attribution. |
| `setup_rapl.sh` | One-time `sudo` helper to make Intel RAPL energy counters readable. |
| `assets/Schwarzsee.jpg` | Source image — a freely-licensed photograph of **Durdle Door, Dorset, UK** (JJ Perks, Pexels), resized to 6144×3456. |
| `tests/` | Unit tests (config, payloads, CSV writer, measurement protocol, skip logic) — no databases required. |

Four operations are measured per *(engine, resolution)*: **insertion** throughput + storage
amplification, **bulk retrieval** (read back all 2,000 images in a time range), **latest-frame
read** (fetch the single most recent image), and **driver** round-trip overhead. One cell is
skipped by design — **MongoDB at 6K** — because time-series bucketing packs several
multi-megabyte frames into one bucket document that breaches the hard **16 MiB** BSON limit (a
single 6K frame, at 7.1 MB, would fit); this is retried, then recorded in `data/skipped.csv`.

(For the full CLI and all environment-variable knobs, see [`code/README.md`](code/README.md).)

---

## The data (`data/`)

All CSVs are generated by `run.py`; `<engine>` ∈ `{postgres, mongo, postgres_minio}`,
`<res>` ∈ `{360p, 480p, 720p, 1080p, 1440p, 4k, 5k, 6k}` (Mongo omits `6k`).

| File pattern | Contents |
|---|---|
| `results_<engine>_insert_runs_<res>.csv` / `_summary_<res>.csv` | Per-run and summary **insertion** metrics: rows/s, durations, on-disk sizes, and **storage amplification** (on-disk ÷ raw payload). |
| `results_<engine>_retrieve_runs_<res>.csv` / `_summary_<res>.csv` | **Bulk-retrieval** latency (ms) for materialising all 2,000 payloads in a time range. |
| `results_<engine>_point_read_runs_<res>.csv` / `_summary_<res>.csv` | **Latest-frame read** latency (ms). |
| `results_<engine>_driver_summary.csv` | Minimal client–server round-trip overhead (ms). |
| `emissions.csv` | CodeCarbon output, one row per `project_name = <engine>_<operation>_<resolution>`: `duration`, `energy_consumed` (kWh), `cpu_energy`, `ram_energy`, `emissions` (kg CO₂eq), grid intensity, host info. **Per-resolution carbon = sum of the insert + retrieve + point\_read rows × 10⁶ (kg→mg), divided by the repetition count.** Each tracker encloses a whole measurement cell — warm-up, the reset before every repetition, the repetitions, and the accounting queries between them — so the result is an *amortised per-run cost*, not the energy of one isolated operation. |
| `threeway_summary.csv` | The aggregated headline table (one row per resolution): each engine's insert rows/s, storage amp, retrieval ms, point-read ms, and total carbon (mg). Built by `report.py`. |
| `skipped.csv` | Cells attempted and abandoned (engine, resolution, attempts, error). `data/` records MongoDB at 6K (BSON bucket limit); `data_collage_i7/` records MongoDB at 4K, killed by the kernel under memory pressure. **A failed cell still leaves a partial row in `emissions.csv`**, so anything reading that log must exclude these first — otherwise MongoDB's 6K point plots as merely cheap rather than infeasible. |

Figures in `figures/` (PDF, vector) are: `insert_throughput`, `retrieval_latency`,
`point_read_latency`, `storage_amplification`, `carbon_per_resolution`, `carbon_breakdown`,
and, for the real-case study, `realframes_carbon`, `crossover_collage`, `crossover_realcase`,
and `applied_annual`.

---

## The real-case corpus (`code_realcase/`)

The controlled benchmark stores one image in every row. Real cameras do not, and the
difference is measurable: MongoDB compresses *across* rows, so identical rows all but
vanish under its bucketing, while PostgreSQL and MinIO compress per value and per object
and are unaffected. To quantify that, `code_realcase/` records a corpus of real frames
from a face-recognition-based attendance system and the benchmark is re-run against it.

```bash
cd code_realcase
python3 launcher.py                          # camera wall with live view and recording
python3 record.py --all --minutes 10 --fps 5 # unattended: every camera, into payloads/
```

Recording writes numbered JPEGs at quality 90, the same encoder and quality the benchmark
uses, then checks every saved frame for faces so a corpus intended for release is verified
rather than assumed to be free of personal data. See `code_realcase/README.md` for the
camera settings and troubleshooting.

---

## 1. Prerequisites

- **Docker** + **Docker Compose** (runs the three databases).
- **Python 3.11+** — `run.py` creates a local `.venv` and installs `requirements.txt` on first launch (set `IOTBENCH_NO_VENV=1` to use the current interpreter).
- **TeX Live** with `latexmk` + `bibtex` (to build the paper). `sn-jnl.cls`/`sn-*.bst` are bundled in `paper/`.
- *(Optional)* **Intel RAPL** for true hardware energy; otherwise CodeCarbon falls back to TDP estimates.

---

## 2. Reproduce the data and figures

```bash
cd code

# one-time: make Intel RAPL energy counters readable (self-elevates with sudo).
# Skip this if you accept CodeCarbon's TDP-estimate fallback.
bash setup_rapl.sh

# full sweep (360p -> 6K, all three engines), then build the report + figures:
python run.py --report
#   -> ../data/    results_*_summary_*.csv, emissions.csv, threeway_summary.csv, skipped.csv
#   -> ../figures/ insert_throughput.pdf, retrieval_latency.pdf, point_read_latency.pdf,
#                  storage_amplification.pdf, carbon_per_resolution.pdf, carbon_breakdown.pdf

python report_realcase.py             # the four two-corpus / two-host figures
```

Useful variants:

```bash
python run.py 1080p 4k 6k             # only these resolutions
python run.py 4k --engines mongodb    # one resolution, one engine
python run.py --no-docker 4k          # services already running
python run.py --dry-run               # print the plan and exit
python report.py                      # rebuild figures + threeway_summary from existing data
```

### Running against the real-case corpus

The payload source is chosen with `BENCHMARK_PAYLOAD_SOURCE`, and each source writes to
its own directory so the published `data/` can never be overwritten:

| Setting | Payload | Output |
|---|---|---|
| `collage` *(default)* | one image, repeated in every row | `data/` |
| `frames` | a different real frame in every row, one camera | `data_frames/` |
| `fleet` | several cameras interleaved at their native resolutions | `data_fleet/` |

```bash
# one camera, real frames, at the resolutions its recording can supply
BENCHMARK_PAYLOAD_SOURCE=frames \
BENCHMARK_FRAMES_DIR=$(realpath ../code_realcase/corpus/<session>/Tapo_IP_Cam) \
BENCHMARK_DATA_DIR=$(realpath ..)/data_frames_tapo \
  python run.py 360p 480p 720p 1080p

# every camera in a recording session, each at the resolutions it can supply
bash run_realcase.sh --dry-run --fleet   # print the plan
bash run_realcase.sh --fleet             # run it
```

A recording session holds one folder per camera, named after the camera with any network or
device address removed: `Tapo_IP_Cam`, `Webcam_1`, `Webcam_2`. `run_realcase.sh` maps each to
its own output folder (`data_frames_tapo`, `data_frames_webcam1`, `data_frames_webcam2`) and to
the resolutions that camera can actually supply.

Nothing is ever upscaled: a camera is only run at resolutions at or below what it actually
captured, because enlarging a frame invents detail the sensor never saw and would change
the JPEG entropy the measurements depend on.

MongoDB at 6K is **automatically skipped** (16 MiB BSON bucket limit) and logged to
`data/skipped.csv`; PostgreSQL and the hybrid still run at 6K.

Run the tests (no databases needed):

```bash
cd code && python -m unittest discover -s tests
```

---

## 3. Build the paper

```bash
cd paper
latexmk -pdf -interaction=nonstopmode main.tex   # runs pdflatex + bibtex -> main.pdf
latexmk -c                                        # remove aux files (keep main.pdf)
```

Figures are read from `../figures/`; the bibliography is `references.bib`. The class and
bibliography styles (`sn-jnl.cls`, `sn-basic.bst`, …) are bundled in `paper/`, so no extra
Springer package install is needed.

---

## 4. Cover letter (optional)

```bash
cd cover_letter
latexmk -pdf cover_letter.tex
```

---

## Notes

- **Source image:** `code/assets/Schwarzsee.jpg` is a photograph of Durdle Door (Dorset, UK)
  by JJ Perks via Pexels (free-use licence), resized to 6144×3456; it is cited in the paper.
- **Configuration:** workload size and ports are env-var configurable
  (`BENCHMARK_TOTAL_ROWS`, `BENCHMARK_BATCH_SIZE`, `BENCHMARK_INSERT_RUNS`, `POSTGRES_PORT`,
  `MONGO_URI`, `MINIO_ENDPOINT`, …) — see [`code/README.md`](code/README.md).
- **Exact environment** (CPU, OS, database, and library versions) used for the reported
  numbers is documented in the paper's environment table.

---

## Citation

If you use this artifact or its data, please cite the accompanying paper:

> A. Yohannis and A. Waworuntu, *Carbon Footprint and Carbon-Aware Selection of
> Document-Oriented, Relational, and Hybrid Object-Relational Storage for Image-Based
> Time-Series Workloads in Green IoT*, Environment Systems and Decisions (under review).

The source image `code/assets/Schwarzsee.jpg` is a photograph of Durdle Door, Dorset, UK,
by JJ Perks via [Pexels](https://www.pexels.com/photo/bay-with-orange-seashore-under-white-and-gray-clouds-8567869/)
(free-use licence). The filename is historical and does not describe the image; it is kept so
that the file hash matches the one used to generate the shipped CSVs.
