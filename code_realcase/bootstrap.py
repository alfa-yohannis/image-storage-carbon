"""Creates the local .venv and restarts the calling script inside it.

Why this module exists
----------------------
The app needs OpenCV, Pillow and python-dotenv, which are installed into a
private .venv folder rather than system-wide. A script started with the system
Python therefore cannot import them, and fails with "No module named 'dotenv'".

Every entry point calls ``ensure_venv()`` as its first action. On the first run
it builds the .venv, installs requirements.txt, and re-executes the script with
the venv's Python; afterwards it returns immediately. This is why any of the
scripts can be started with a plain ``python3 <script>.py`` and simply work.

Set CAMWALL_NO_VENV=1 to skip it and use whatever packages are already present.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
VENV_DIR = HERE / ".venv"
VENV_PYTHON = VENV_DIR / "bin" / "python"


def in_venv() -> bool:
    """True when the current interpreter is already this project's .venv."""
    try:
        return VENV_DIR.exists() and VENV_DIR.resolve() == Path(sys.prefix).resolve()
    except OSError:
        return False


def install_requirements() -> None:
    """Install requirements.txt, but only when it has changed since last time.

    The file is hashed and a marker named after that hash is left behind. If the
    marker exists the packages are current, so nothing is reinstalled and start-up
    stays fast.
    """
    requirements = HERE / "requirements.txt"
    if not requirements.exists():
        return

    digest = hashlib.md5(requirements.read_bytes()).hexdigest()
    marker = VENV_DIR / (".deps-" + digest)
    if marker.exists():
        return

    print("[setup] installing packages from requirements.txt ...")
    subprocess.run([str(VENV_PYTHON), "-m", "pip", "install", "-r", str(requirements)], check=True)

    for old_marker in VENV_DIR.glob(".deps-*"):
        old_marker.unlink()
    marker.touch()


def ensure_venv(script_name: str) -> None:
    """Build the .venv if needed, then re-run script_name inside it.

    Does nothing when already running in the venv, or when CAMWALL_NO_VENV=1.
    The call does not return when a restart happens: execve replaces this
    process, and everything after the call runs in the new one.
    """
    if os.environ.get("CAMWALL_NO_VENV") == "1":
        return
    if os.environ.get("CAMWALL_IN_VENV") == "1" or in_venv():
        return

    if not VENV_PYTHON.exists():
        print("[setup] creating virtual environment:", VENV_DIR)
        subprocess.run([sys.executable, "-m", "venv", str(VENV_DIR)], check=True)
        subprocess.run([str(VENV_PYTHON), "-m", "pip", "install", "-q", "--upgrade", "pip"], check=True)

    install_requirements()

    environment = dict(os.environ, CAMWALL_IN_VENV="1")
    os.execve(
        str(VENV_PYTHON),
        [str(VENV_PYTHON), str(HERE / script_name)] + sys.argv[1:],
        environment,
    )
