#!/usr/bin/env python3
"""Launcher for the camera wall: checks everything is ready, then starts app.py.

Running app.py directly works too, but when something is missing OpenCV and Tk
report it in a way that is hard to read. This launcher checks the common
problems first and explains each one in plain language:

    - Tkinter is missing (it cannot be installed with pip)
    - there is no screen to draw on
    - the .env file has not been created yet
    - no camera is configured

Usage:
    python3 launcher.py                 # check, then start the camera wall
    python3 launcher.py --check         # run the checks only, do not start
    python3 launcher.py --only webcam   # any app.py option is passed straight through
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

APP = HERE / "app.py"
ENV_FILE = HERE / ".env"
ENV_EXAMPLE = HERE / ".env.example"


class Check:
    """One thing that must be true before the app can start.

    Fields:
        name:   short label shown to the user.
        passed: True when the requirement is met.
        hint:   what to do about it when it is not met.
        fatal:  True if the app cannot start at all without it.
    """

    def __init__(self, name: str, passed: bool, hint: str = "", fatal: bool = True) -> None:
        """Record the outcome of one check."""
        self.name = name
        self.passed = passed
        self.hint = hint
        self.fatal = fatal

    def describe(self) -> str:
        """Return one line of report text, marked ok, warning, or failed."""
        if self.passed:
            return "  [ ok ] " + self.name
        if self.fatal:
            return "  [FAIL] " + self.name + "\n         " + self.hint
        return "  [warn] " + self.name + "\n         " + self.hint


class Preflight:
    """Runs every check and reports whether the app can start."""

    def __init__(self) -> None:
        """Prepare an empty list of results."""
        self.checks: list[Check] = []

    def run(self) -> bool:
        """Perform all checks and return True if none of the fatal ones failed."""
        self.checks = [
            self._check_python(),
            self._check_tkinter(),
            self._check_display(),
            self._check_env_file(),
            self._check_cameras(),
        ]

        print("Camera wall - pre-flight checks")
        for check in self.checks:
            print(check.describe())
        print()

        for check in self.checks:
            if check.fatal and not check.passed:
                return False
        return True

    def _check_python(self) -> Check:
        """The app uses the 'str | None' type syntax, added in Python 3.10."""
        version = sys.version_info
        passed = version >= (3, 10)
        readable = "{}.{}.{}".format(version.major, version.minor, version.micro)
        return Check(
            "Python " + readable,
            passed,
            "Python 3.10 or newer is required.",
        )

    def _check_tkinter(self) -> Check:
        """Tkinter ships with Python on most systems but is a separate package on Linux."""
        try:
            import tkinter  # noqa: F401

            passed = True
        except ImportError:
            passed = False

        return Check(
            "Tkinter available",
            passed,
            "Tkinter cannot be installed with pip. On Debian or Ubuntu run:\n"
            "             sudo apt install python3-tk",
        )

    def _check_display(self) -> Check:
        """A desktop window needs a screen; over plain SSH there is none."""
        passed = bool(os.environ.get("DISPLAY") or os.environ.get("WAYLAND_DISPLAY"))
        return Check(
            "Screen available",
            passed,
            "No DISPLAY or WAYLAND_DISPLAY is set. Run this on the computer's own\n"
            "             desktop, or use 'ssh -X' to forward the window.",
        )

    def _check_env_file(self) -> Check:
        """Without .env there are no camera details to read."""
        passed = ENV_FILE.exists()
        return Check(
            ".env file present",
            passed,
            "Create it by copying the example, then fill in your camera details:\n"
            "             cp .env.example .env",
        )

    def _check_cameras(self) -> Check:
        """Warn, but do not stop, when nothing is configured yet.

        This import only works once .env exists, so a missing file is reported
        as "unknown" rather than as a second failure.
        """
        if not ENV_FILE.exists():
            return Check("Cameras configured", False, "Cannot check until .env exists.", fatal=False)

        try:
            from config import Config

            cameras = Config().cameras()
        except Exception as error:
            return Check("Cameras configured", False, "Could not read .env: " + str(error), fatal=False)

        if not cameras:
            return Check(
                "Cameras configured",
                False,
                "No cameras found in .env. Set IP_ADDRESS and the TAPO_ values,\n"
                "             or WEBCAM_1_INDEX and WEBCAM_2_INDEX.",
                fatal=False,
            )

        names = ", ".join(camera.name for camera in cameras)
        return Check("Cameras configured (" + str(len(cameras)) + "): " + names, True)


def start_app(passthrough: list[str]) -> int:
    """Start app.py, forwarding any extra command-line options to it.

    app.py builds its own .venv and restarts itself inside it, so we simply run
    it with the Python we already have.
    """
    command = [sys.executable, str(APP)] + passthrough
    print("Starting the camera wall ...")
    result = subprocess.run(command)
    return result.returncode


def main() -> int:
    """Run the checks, then start the app unless --check was given."""
    arguments = sys.argv[1:]

    check_only = "--check" in arguments
    if check_only:
        arguments.remove("--check")

    if not APP.exists():
        print("Cannot find app.py next to this launcher.", file=sys.stderr)
        return 1

    preflight = Preflight()
    ready = preflight.run()

    if not ready:
        print("Fix the items marked FAIL above, then run this launcher again.")
        return 1

    if check_only:
        print("All checks passed. Run without --check to start the camera wall.")
        return 0

    return start_app(arguments)


if __name__ == "__main__":
    sys.exit(main())
