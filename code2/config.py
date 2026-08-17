"""Reads the camera settings from the .env file.

This is the only module that looks at environment variables. Everything else in
the app receives ready-made Camera objects, so no other file needs to know how
the settings are stored.

Keeping the settings in .env (instead of writing them in the code) means the
camera password never appears in a source file that might be shared or committed.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

from dotenv import load_dotenv

# Path(__file__) is this file; .parent is the folder holding it. We build paths
# from here so the app works no matter which folder you run it from.
HERE = Path(__file__).resolve().parent
ENV_PATH = HERE / ".env"

# An IP camera sends video over the network using a protocol called RTSP.
# By default it travels over UDP, which is fast but drops pieces of the picture
# on a busy Wi-Fi network. Asking for TCP instead gives a cleaner image.
# OpenCV reads this setting when a camera is opened, so we set it here at import.
os.environ.setdefault("OPENCV_FFMPEG_CAPTURE_OPTIONS", "rtsp_transport;tcp")

# The two kinds of camera this app supports.
IP_CAMERA = "ipcam"
WEBCAM = "webcam"


@dataclass(frozen=True)
class Camera:
    """Describes one camera.

    A dataclass is a class whose job is simply to hold values. Python writes the
    __init__ method for us from the fields listed below.

    Fields:
        name:    label shown above the video, e.g. "Webcam 1".
        kind:    either IP_CAMERA or WEBCAM.
        address: for an IP camera, the rtsp:// link; for a webcam, the number of
                 the device, where 0 means /dev/video0.
        width:   requested picture width, or 0 to accept whatever the camera gives.
        height:  requested picture height, or 0 for the camera's own default.
        fps:     how many pictures per second to keep, or 0 to keep them all.

    Note that fps is applied by our own code, not by the camera. Most webcams
    ignore a request to run slower, so the only way to reach a chosen rate is to
    read every picture and keep just the ones that are due.

    "frozen=True" makes a Camera read-only once created, so no other part of the
    program can change a camera's address by accident.
    """

    name: str
    kind: str
    address: str | int
    width: int = 0
    height: int = 0
    fps: int = 0

    def is_ip_camera(self) -> bool:
        """Return True if this is a network camera, False if it is a USB webcam."""
        return self.kind == IP_CAMERA

    def safe_address(self) -> str:
        """Return the address with the password hidden, so it is safe to display.

        An RTSP link looks like rtsp://user:password@192.168.0.5:554/stream1.
        Showing that on screen would reveal the password, so we replace it
        with **** before the address is printed or drawn in the window.
        """
        text = str(self.address)

        # A webcam address is just a number, and a link without "@" carries no
        # password. In both cases there is nothing to hide.
        if "://" not in text or "@" not in text:
            return text

        scheme, rest = text.split("://", 1)
        credentials, host = rest.rsplit("@", 1)
        user = credentials.split(":", 1)[0]
        return scheme + "://" + user + ":****@" + host


class Config:
    """Loads the .env file once and answers questions about the settings."""

    def __init__(self, env_path: Path = ENV_PATH) -> None:
        """Read the .env file and remember the display settings.

        If the file is missing, the default values below are used instead, so
        the app still starts.
        """
        load_dotenv(env_path)
        self.target_fps = self._read_number("TARGET_FPS", 25)
        self.webcam_width = self._read_number("WEBCAM_WIDTH", 1280)
        self.webcam_height = self._read_number("WEBCAM_HEIGHT", 720)
        self.snapshot_dir = HERE / "snapshots"
        self.payload_dir = HERE / "payloads"

        # How long the Start button records for, and how many pictures a second
        # it keeps. Recording stops at this limit or when Stop is pressed.
        self.record_minutes = self._read_decimal("RECORD_MINUTES", 10.0)
        self.record_fps = self._read_number("RECORD_FPS", 5)

        # Detection draws the green boxes. Recognition additionally puts a name
        # on each box, and only works once photos are placed in known_faces/.
        self.face_detection = self._read_flag("FACE_DETECTION", True)
        self.face_recognition = self._read_flag("FACE_RECOGNITION", False)

        # How sure the detector must be, from 0 to 1. Lower it if faces are
        # missed, raise it if things that are not faces get boxed.
        self.face_min_confidence = self._read_decimal("FACE_MIN_CONFIDENCE", 0.5)

    def cameras(self) -> list[Camera]:
        """Build the list of cameras to show: one IP camera and two webcams.

        A camera that is switched off or unplugged is still included. The window
        shows it as "disconnected" and keeps trying to reach it, which is what
        you want for a wall of cameras that come and go during the day.
        """
        cameras = []

        url = self.ip_camera_url()
        if url:
            host = self._read_text("IP_ADDRESS")
            if not host:
                host = "IP camera"
            cameras.append(
                Camera(
                    name="Tapo IP Cam (" + host + ")",
                    kind=IP_CAMERA,
                    address=url,
                    fps=self._read_number("IPCAM_FPS", 0),
                )
            )

        # Webcam 1 normally sits at /dev/video0 and webcam 2 at /dev/video2,
        # because each physical camera usually claims two device numbers.
        default_indexes = {1: 0, 2: 2}
        for slot in (1, 2):
            prefix = "WEBCAM_" + str(slot) + "_"
            index = self._read_number(prefix + "INDEX", default_indexes[slot])
            name = "Webcam " + str(slot) + " (/dev/video" + str(index) + ")"

            # Each webcam may set its own size; WEBCAM_WIDTH and WEBCAM_HEIGHT
            # remain the fallback for both, so old .env files still work.
            cameras.append(
                Camera(
                    name=name,
                    kind=WEBCAM,
                    address=index,
                    width=self._read_number(prefix + "WIDTH", self.webcam_width),
                    height=self._read_number(prefix + "HEIGHT", self.webcam_height),
                    fps=self._read_number(prefix + "FPS", 0),
                )
            )

        return cameras

    def ip_camera_url(self) -> str | None:
        """Build the rtsp:// link for the Tapo camera, or return None if unset.

        Returning None instead of raising an error lets the app run with only the
        webcams when no IP camera is configured.
        """
        # IPCAM_URL lets you paste a complete link for any brand of camera and
        # skip the Tapo-specific settings entirely.
        explicit_url = self._read_text("IPCAM_URL")
        if explicit_url:
            return explicit_url

        host = self._read_text("IP_ADDRESS")
        user = self._read_text("TAPO_USERNAME")
        password = self._read_text("TAPO_PASSWORD")

        # Without all three we cannot build a valid link.
        if not host or not user or not password:
            return None

        stream = self._read_text("TAPO_STREAM")
        if not stream:
            stream = "stream1"
        port = self._read_number("TAPO_RTSP_PORT", 554)

        # The user name and password sit inside a web address, where characters
        # such as @ : and / have a special meaning. quote() rewrites them into a
        # safe form, so a password like "p@ss/word" does not break the link.
        user = quote(user, safe="")
        password = quote(password, safe="")

        return "rtsp://" + user + ":" + password + "@" + host + ":" + str(port) + "/" + stream

    def _read_text(self, key: str) -> str:
        """Return one setting as text, or an empty string when it is not set.

        The leading underscore is a Python convention meaning "internal helper":
        other modules should not call this.
        """
        value = os.getenv(key, "")
        return value.strip()

    def _read_decimal(self, key: str, default: float) -> float:
        """Return a setting that may have a decimal point, such as 0.5."""
        text = self._read_text(key)
        if not text:
            return default
        try:
            return float(text)
        except ValueError:
            return default

    def _read_flag(self, key: str, default: bool) -> bool:
        """Return a yes/no setting. Accepts 1, true, yes, or on, in any case."""
        text = self._read_text(key).lower()
        if not text:
            return default
        return text in ("1", "true", "yes", "on")

    def _read_number(self, key: str, default: int) -> int:
        """Return one setting as a whole number, or the default if it is missing.

        A typo such as TARGET_FPS=abc would crash int(), so we catch that and
        fall back to the default rather than stopping the whole app.
        """
        text = self._read_text(key)
        if not text:
            return default
        try:
            return int(text)
        except ValueError:
            return default
