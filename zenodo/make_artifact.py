#!/usr/bin/env python3
"""Build the versioned, anonymised reproducibility artifact.

The archive is split so that reviewers who only want to check the analysis do
not have to download a gigabyte of photographs:

    artifact-vX.Y.zip        code, data, figures, and paper source  (~10 MB)
    frames-<camera>-vX.Y.zip the recorded frames, one archive per camera

Every archive unpacks into the same directory tree, so extracting all four on
top of one another reconstitutes the working repository.

Anonymisation is applied here rather than assumed, because the submission is
double-anonymous and the raw working tree is not:

  * CodeCarbon writes the machine's latitude, longitude, and administrative
    region into every emissions.csv. Those columns are blanked; the country is
    kept, because the paper's grid-intensity factor depends on it.
  * Credentials, virtual environments, downloaded models, and enrolled face
    photographs are excluded outright.

Usage:  python3 make_artifact.py [--version 2.0] [--no-frames]
"""

from __future__ import annotations

import argparse
import csv
import io
import shutil
import tempfile
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

# Columns CodeCarbon fills with the measuring machine's location. Blanked, not
# dropped, so the CSV keeps the schema a reader of the tool would expect.
LOCATION_COLUMNS = ("latitude", "longitude", "region")

# Never copied, wherever they appear in the tree.
EXCLUDED_NAMES = {
    ".venv", "__pycache__", ".git", ".pytest_cache", ".mypy_cache",
    ".env",             # camera and database credentials
    "models",           # 38 MB of ONNX, fetched by download_models.sh
    "known_faces",      # enrolled photographs are biometric personal data
    "snapshots",
    "corpus",           # shipped separately, one archive per camera
    "payloads",         # working copy of the corpus
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".log"}

# Working copies of the recorded corpus, kept where config.py looks for them by
# default. The frames themselves ship in their own per-camera archives, so
# including these would put the same 450 MB in the artifact twice.
EXCLUDED_PREFIXES = ("assets/frames", "assets/fleet")

# What goes into the main archive, as (source, destination-inside-zip).
CONTENTS = [
    ("code", "code"),
    ("code_realcase", "code_realcase"),
    ("data", "data"),
    ("data_collage_i7", "data_collage_i7"),
    ("data_frames_tapo", "data_frames_tapo"),
    ("data_frames_webcam1", "data_frames_webcam1"),
    ("data_frames_webcam2", "data_frames_webcam2"),
    ("data_fleet", "data_fleet"),
    ("figures", "figures"),
]
PAPER_FILES = ["main.tex", "references.bib", "sn-jnl.cls", "sn-basic.bst", "main.bbl"]

# Recorded corpus: folder in the working tree -> archive name for its zip.
CAMERAS = {
    "Tapo_IP_Cam": "networked",
    "Webcam_2": "usb-external",
    "Webcam_1": "usb-builtin",
}


def is_excluded(path: Path) -> bool:
    """True when this path, or any folder above it, must not be published."""
    if path.suffix in EXCLUDED_SUFFIXES:
        return True
    if path.as_posix().startswith(EXCLUDED_PREFIXES):
        return True
    return any(part in EXCLUDED_NAMES for part in path.parts)


def sanitise_emissions(path: Path) -> bytes:
    """Return emissions.csv with the machine's location removed."""
    rows = list(csv.DictReader(path.open()))
    if not rows:
        return path.read_bytes()
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]), lineterminator="\n")
    writer.writeheader()
    for row in rows:
        for column in LOCATION_COLUMNS:
            if column in row:
                row[column] = ""
        writer.writerow(row)
    return buffer.getvalue().encode()


def stage(version: str) -> Path:
    """Copy everything the main archive needs into a clean temporary tree."""
    staging = Path(tempfile.mkdtemp(prefix="artifact-")) / f"artifact-v{version}"
    staging.mkdir(parents=True)

    for source_name, target_name in CONTENTS:
        source = ROOT / source_name
        if not source.exists():
            print(f"  ! missing, skipped: {source_name}")
            continue
        for item in sorted(source.rglob("*")):
            relative = item.relative_to(source)
            if is_excluded(relative) or item.is_dir():
                continue
            target = staging / target_name / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            if item.name == "emissions.csv":
                target.write_bytes(sanitise_emissions(item))
            else:
                shutil.copy2(item, target)

    paper_dir = staging / "paper"
    paper_dir.mkdir(parents=True, exist_ok=True)
    for name in PAPER_FILES:
        source = ROOT / "paper" / name
        if source.exists():
            shutil.copy2(source, paper_dir / name)
        else:
            print(f"  ! missing, skipped: paper/{name}")
    shutil.copytree(ROOT / "figures", paper_dir / "figures", dirs_exist_ok=True)

    shutil.copy2(HERE / "README.md", staging / "README.md")
    return staging


def write_zip(target: Path, tree: Path, arc_root: str) -> None:
    """Zip a directory tree, deflating text and storing already-compressed media."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        for item in sorted(tree.rglob("*")):
            if item.is_dir():
                continue
            arcname = Path(arc_root) / item.relative_to(tree)
            method = zipfile.ZIP_STORED if item.suffix.lower() in {".jpg", ".jpeg", ".png"} \
                else zipfile.ZIP_DEFLATED
            archive.write(item, arcname, compress_type=method)


def megabytes(path: Path) -> str:
    return f"{path.stat().st_size / 1e6:.1f} MB"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", default="2.0", help="version stamped into the filenames")
    parser.add_argument("--no-frames", action="store_true",
                        help="build only the main archive, skipping the recorded frames")
    args = parser.parse_args()
    version = args.version

    print(f"Building reproducibility artifact v{version}\n")

    staging = stage(version)
    main_zip = HERE / f"artifact-v{version}.zip"
    write_zip(main_zip, staging, ".")
    count = sum(1 for _ in staging.rglob("*") if _.is_file())
    print(f"  {main_zip.name:38s} {megabytes(main_zip):>10s}  ({count} files)")
    shutil.rmtree(staging.parent)

    if args.no_frames:
        print("\n  frames skipped (--no-frames)")
        return

    sessions = sorted((ROOT / "code_realcase" / "corpus").glob("*"))
    for session in sessions:
        if not session.is_dir():
            continue
        for folder, label in CAMERAS.items():
            source = session / folder
            if not source.is_dir():
                print(f"  ! missing, skipped: {source.name}")
                continue
            target = HERE / f"frames-{label}-v{version}.zip"
            # Keep the full path so every archive unpacks into the same tree.
            arc_root = f"code_realcase/corpus/{session.name}/{folder}"
            write_zip(target, source, arc_root)
            frames = sum(1 for _ in source.glob("*.jpg"))
            print(f"  {target.name:38s} {megabytes(target):>10s}  ({frames} frames)")


if __name__ == "__main__":
    main()
