#!/usr/bin/env python3
"""Unified three-way benchmark runner (OO).

Engines    : MongoDB (inline BSON) | PostgreSQL (BYTEA) | PostgreSQL + MinIO
Dimensions : insert throughput + storage amplification, full-materialisation
             retrieval, latest-payload point-read, driver overhead, and
             per-resolution energy / CO2 (CodeCarbon).
Resolutions: 360p -> 6K.

Each engine phase brings up only the services it needs (isolation), and each
(dimension, resolution) is wrapped in its own CodeCarbon tracker, so
per-resolution carbon is measured directly. Results -> ESD data/ , figures/.

On first launch this script creates a local .venv and installs requirements.txt
automatically (set IOTBENCH_NO_VENV=1 to use the current interpreter instead).

Examples:
    python run.py                          # full 360p->6K sweep, all engines
    python run.py 360p 4k 6k               # only these resolutions
    python run.py 1080p --engines mongodb  # one resolution, one engine
    python run.py --no-docker              # services already running
    python run.py --dry-run 4k 5k          # print the plan and exit
    python run.py --report                 # also build the three-way report
"""
from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))


def _ensure_venv() -> None:
    """On first launch, create ./.venv, install requirements.txt, then re-exec
    inside it so `python run.py ...` works with no manual setup. Skipped when
    IOTBENCH_NO_VENV=1 or when already running inside the venv."""
    if os.environ.get("IOTBENCH_NO_VENV") == "1" or os.environ.get("IOTBENCH_IN_VENV") == "1":
        return
    venv_dir = _HERE / ".venv"
    venv_py = venv_dir / "bin" / "python"
    try:
        if venv_dir.resolve() == Path(sys.prefix).resolve():
            return  # already running inside the venv
    except OSError:
        pass
    if not venv_py.exists():
        print(f"[bootstrap] creating virtualenv: {venv_dir}")
        subprocess.run([sys.executable, "-m", "venv", str(venv_dir)], check=True)
        subprocess.run([str(venv_py), "-m", "pip", "install", "-q", "--upgrade", "pip"], check=True)
    req = _HERE / "requirements.txt"
    if req.exists():
        marker = venv_dir / f".deps-{hashlib.md5(req.read_bytes()).hexdigest()}"
        if not marker.exists():
            print("[bootstrap] installing dependencies from requirements.txt ...")
            subprocess.run([str(venv_py), "-m", "pip", "install", "-r", str(req)], check=True)
            for stale in venv_dir.glob(".deps-*"):
                stale.unlink()
            marker.touch()
    os.execve(str(venv_py), [str(venv_py), str(_HERE / "run.py"), *sys.argv[1:]],
              dict(os.environ, IOTBENCH_IN_VENV="1"))


_ensure_venv()

import argparse  # noqa: E402  (heavy/third-party imports come after venv bootstrap)
import time  # noqa: E402

from carbon import CarbonTracker  # noqa: E402
from config import DEFAULT_SWEEP, Locations, Settings, resolve_profile  # noqa: E402
from engine_mongodb import MongoEngine  # noqa: E402
from engine_postgres import PostgresEngine  # noqa: E402
from engine_postgres_minio import PostgresMinioEngine  # noqa: E402
from payloads import PayloadFactory  # noqa: E402
from results import ResultWriter  # noqa: E402

ENGINE_REGISTRY = {
    "postgres": PostgresEngine,
    "postgres_minio": PostgresMinioEngine,
    "mongodb": MongoEngine,
}


def _fmt(seconds: float) -> str:
    """Format a duration as HH:MM:SS."""
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def _warn_if_rapl_unreadable() -> None:
    """If Intel RAPL exists but its energy counters aren't readable, point the
    user at setup_rapl.sh (CodeCarbon otherwise falls back to TDP estimates)."""
    base = Path("/sys/devices/virtual/powercap")
    if not base.exists():
        return  # no Intel RAPL (VM / non-Intel) — CodeCarbon estimates anyway
    energy_files = list(base.glob("**/energy_uj"))
    if not energy_files:
        return
    for f in energy_files:
        try:
            f.read_text()
            return  # at least one readable -> RAPL works
        except OSError:
            continue
    print("\n[warn] Intel RAPL energy counters are not readable -> CodeCarbon will use "
          "TDP estimates, not hardware measurement.")
    print(f"       Enable real measurement once with:   bash {_HERE / 'setup_rapl.sh'}")
    print("       (or pass --no-carbon to skip energy tracking)\n")


class DockerCompose:
    def __init__(self, code_dir: Path, enabled: bool = True):
        self.code_dir = Path(code_dir)
        self.compose_file = self.code_dir / "docker-compose.yml"
        self.enabled = enabled

    def _run(self, *args: str) -> None:
        subprocess.run(["docker", "compose", "-f", str(self.compose_file), *args],
                       cwd=str(self.code_dir), check=True)

    def up(self, services: tuple[str, ...]) -> None:
        if self.enabled:
            self._run("up", "-d", *services)

    def down(self) -> None:
        if self.enabled:
            self._run("down", "-v", "--remove-orphans")


def _measure_cell(engine, payload, engine_name: str, profile: str,
                  carbon_enabled: bool, data_dir: Path) -> dict:
    """Run all four dimensions for one (engine, resolution) cell and return the
    in-memory results. Nothing is persisted here: an exception raised by any
    dimension (e.g. a payload the engine cannot store) aborts the whole cell so
    the caller can retry without leaving partial CSV rows behind."""
    def step(label, fn, carbon_name=None):
        started = time.perf_counter()
        print(f"   - {label} ...", flush=True)
        if carbon_name:
            with CarbonTracker(carbon_name, data_dir, carbon_enabled):
                result = fn()
        else:
            result = fn()
        print(f"   - {label} done in {_fmt(time.perf_counter() - started)}")
        return result

    return {
        "driver": step("driver overhead", engine.run_driver),
        "insert": step("insert", lambda: engine.run_insert(payload), f"{engine_name}_insert_{profile}"),
        "retrieval": step("retrieval", engine.run_retrieval, f"{engine_name}_retrieve_{profile}"),
        "point_read": step("point-read", lambda: engine.run_point_read(payload),
                           f"{engine_name}_point_read_{profile}"),
    }


def run_engine(engine_name: str, profiles: list[str], compose: DockerCompose,
               writer: ResultWriter, carbon_enabled: bool, data_dir: Path,
               run_start: float, progress: dict, max_attempts: int) -> None:
    cls = ENGINE_REGISTRY[engine_name]
    phase_start = time.perf_counter()
    print(f"\n############ PHASE: {engine_name}  "
          f"(elapsed {_fmt(time.perf_counter() - run_start)}) ############")
    compose.down()
    compose.up(cls.services)

    probe = cls(Settings.load(profiles[0]))
    probe.wait_ready()
    probe.close()

    for profile in profiles:
        settings = Settings.load(profile)
        payload = PayloadFactory(settings.locations.source_image_path).build(settings.workload)
        gidx = progress["done"] + 1
        profile_start = time.perf_counter()
        print(f"\n==== [{gidx}/{progress['total']}] {engine_name} :: {profile}  "
              f"({payload.payload_size_mb:.2f} MB/sample) ====")

        # Retry-then-skip: measure into memory, persist only on a fully clean
        # attempt. After `max_attempts` failures, record the skip and move on so
        # one unstorable cell never aborts the sweep.
        engine = cls(settings)
        error = None
        for attempt in range(1, max_attempts + 1):
            try:
                results = _measure_cell(engine, payload, engine_name, profile, carbon_enabled, data_dir)
                writer.write_driver(engine, settings, results["driver"])
                writer.write_insert(engine, settings, payload, results["insert"])
                writer.write_retrieval(engine, settings, payload, results["retrieval"])
                writer.write_point_read(engine, settings, payload, results["point_read"])
                error = None
                break
            except Exception as exc:  # any engine/measurement failure
                error = exc
                print(f"   ! {engine_name}:{profile} attempt {attempt}/{max_attempts} failed: "
                      f"{type(exc).__name__}: {str(exc)[:160]}")
                engine.close()
                if attempt < max_attempts:
                    engine = cls(settings)  # fresh connection for the next attempt
        engine.close()

        progress["done"] = gidx
        elapsed = time.perf_counter() - run_start
        eta = (elapsed / gidx) * (progress["total"] - gidx) if gidx else 0.0
        if error is not None:
            writer.write_skip(engine, settings, payload, max_attempts, error)
            print(f"   [{gidx}/{progress['total']}] {engine_name}:{profile} SKIPPED after "
                  f"{max_attempts} attempt(s) ({type(error).__name__})  |  elapsed {_fmt(elapsed)}  "
                  f"|  ETA {_fmt(eta)}")
        else:
            print(f"   [{gidx}/{progress['total']}] {engine_name}:{profile} done in "
                  f"{_fmt(time.perf_counter() - profile_start)}  |  elapsed {_fmt(elapsed)}  "
                  f"|  ETA {_fmt(eta)}")

    compose.down()
    print(f"############ PHASE {engine_name} finished in {_fmt(time.perf_counter() - phase_start)} ############")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Unified three-way image time-series benchmark.",
        formatter_class=argparse.RawDescriptionHelpFormatter, epilog=__doc__)
    parser.add_argument("resolutions", nargs="*",
                        help="one or more resolutions to run, e.g. 360p 480p 4k 6k "
                             "(default: full 360p->6K sweep)")
    parser.add_argument("--engines", default="postgres,postgres_minio,mongodb",
                        help="comma-separated subset of: postgres,postgres_minio,mongodb")
    parser.add_argument("--profiles", default="",
                        help="comma-separated resolutions (alias for the positional args)")
    parser.add_argument("--no-docker", action="store_true",
                        help="assume services already running; do not manage docker compose")
    parser.add_argument("--no-carbon", action="store_true", help="disable CodeCarbon tracking")
    parser.add_argument("--max-attempts", type=int, default=int(os.getenv("BENCHMARK_MAX_ATTEMPTS", "2")),
                        help="attempts per (engine, resolution) before skipping it (default 2)")
    parser.add_argument("--report", action="store_true", help="build the three-way report afterwards")
    parser.add_argument("--dry-run", action="store_true", help="print the resolved plan and exit")
    args = parser.parse_args(argv)
    max_attempts = max(1, args.max_attempts)

    engines = [e.strip() for e in args.engines.split(",") if e.strip()]
    unknown = [e for e in engines if e not in ENGINE_REGISTRY]
    if unknown:
        parser.error(f"unknown engines: {unknown}. choose from {list(ENGINE_REGISTRY)}")

    tokens = list(args.resolutions)
    if not tokens and args.profiles:
        tokens = [t.strip() for t in args.profiles.split(",") if t.strip()]
    if not tokens:
        profiles = list(DEFAULT_SWEEP)
    else:
        profiles = []
        for token in tokens:
            try:
                profiles.append(resolve_profile(token).name)
            except ValueError as exc:
                parser.error(str(exc))

    locations = Locations.create()
    writer = ResultWriter(locations.data_dir)
    compose = DockerCompose(locations.code_dir, enabled=not args.no_docker)

    print(f"Engines = {engines}")
    print(f"Profiles = {profiles}")
    print(f"data    -> {locations.data_dir}")
    print(f"figures -> {locations.figures_dir}")
    if args.dry_run:
        print("(dry run — nothing executed)")
        return

    if not args.no_carbon:
        _warn_if_rapl_unreadable()

    run_start = time.perf_counter()
    progress = {"done": 0, "total": len(engines) * len(profiles)}
    for engine_name in engines:
        run_engine(engine_name, profiles, compose, writer,
                   carbon_enabled=not args.no_carbon, data_dir=locations.data_dir,
                   run_start=run_start, progress=progress, max_attempts=max_attempts)

    if args.report:
        from report import Reporter
        Reporter(locations).build()

    print(f"\nDone in {_fmt(time.perf_counter() - run_start)}. Data in {locations.data_dir}")


if __name__ == "__main__":
    main()
