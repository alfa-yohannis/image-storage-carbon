#!/usr/bin/env python3
"""Records real camera frames as numbered JPEG files, for use as benchmark payloads.

Why this exists
---------------
The storage benchmark in ../code/ builds one synthetic collage and inserts that
same picture thousands of times. Every stored row is therefore byte-identical,
which lets a database compress the repetition in a way it never could with real
data. This tool captures a stream of genuinely different pictures instead, so the
benchmark can be re-run against a realistic payload corpus.

Frames are written as separate JPEG files rather than as a video on purpose. A
video would have to be decoded and re-encoded before each frame could be stored,
which would burn energy inside the measured region, alter the picture's
compressibility, and make the bytes depend on which decoder happened to be
installed. Individual JPEGs are fixed bytes: identical on every machine.

Capture one resolution only - the highest the camera offers - and let the
benchmark derive smaller sizes from it. Every resolution then shows the same
scene at the same instant, so a difference between resolutions is caused by size
alone and not by different content.

Privacy
-------
These are pictures of a real place. When recording is finished, every frame is
checked for faces and any that contain one is reported, so nothing unexpected
ends up in a shared corpus. Record an empty scene when the frames are meant to
be published.

Usage:
    python3 record.py --all                    # every camera, 10 minutes, unattended
    python3 record.py                          # 10 minutes at 5 fps from the IP camera
    python3 record.py --minutes 2 --fps 5      # a short trial run first
    python3 record.py --camera webcam2         # record from a webcam instead
    python3 record.py --no-check               # skip the face sweep at the end

Prefer --all from a terminal for any long recording: there is no window to close
by accident, so nothing can cut the session short.
"""

from __future__ import annotations

import argparse
import sys
import threading
import time
from io import BytesIO
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import cv2
import numpy as np
from PIL import Image

from capture import RATE_TOLERANCE, Stream
from config import Camera, Config
from faces import FaceDetector

# Matches the quality the existing benchmark encodes at, so the new corpus is
# directly comparable with the published results.
JPEG_QUALITY = 90

# How often to print progress, in frames.
PROGRESS_EVERY = 100

# Where recordings go. Each session gets its own dated folder inside this one,
# so a new recording can never overwrite an earlier one.
PAYLOAD_ROOT = HERE / "payloads"


def save_jpeg(image: np.ndarray, path: Path, quality: int = JPEG_QUALITY) -> int:
    """Write one picture as a JPEG file and return how many bytes it took.

    Pillow is used rather than OpenCV's own writer because the existing
    benchmark encodes with Pillow. Using the same encoder keeps the new corpus
    comparable with the published numbers.
    """
    # OpenCV works in Blue-Green-Red order; Pillow expects Red-Green-Blue.
    rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

    buffer = BytesIO()
    Image.fromarray(rgb).save(buffer, format="JPEG", quality=quality)
    data = buffer.getvalue()

    path.write_bytes(data)
    return len(data)


def describe_sizes(sizes: list[int]) -> str:
    """Describe the sizes of a set of frames, for the paper's payload table."""
    if not sizes:
        return "no frames saved"

    total = sum(sizes)
    mean = total / len(sizes)
    return "{} frames, {:.1f} MB, mean {:.0f} KB (range {:.0f}-{:.0f} KB)".format(
        len(sizes),
        total / 1_000_000,
        mean / 1000,
        min(sizes) / 1000,
        max(sizes) / 1000,
    )


def safe_name(text: str) -> str:
    """Turn a camera name into something usable as a folder name."""
    result = ""
    for character in text:
        if character.isalnum():
            result = result + character
        else:
            result = result + "_"
    return result.strip("_")


def session_folder(camera_name: str, stamp: str) -> Path:
    """Return the folder one single-camera recording should write into."""
    return PAYLOAD_ROOT / (stamp + "_" + safe_name(camera_name))


def group_folder(camera_name: str, stamp: str) -> Path:
    """Return the folder one camera writes into when all cameras record together.

    Every camera in the session shares the outer dated folder and gets its own
    subfolder inside it, so the recordings stay grouped as one session:

        payloads/20260817-193000/Tapo_IP_Cam__192_168_43_46/
        payloads/20260817-193000/Webcam_1__dev_video0/
    """
    return PAYLOAD_ROOT / stamp / safe_name(camera_name)


class FrameRecorder:
    """Captures a set number of frames from one camera and saves them as JPEGs."""

    def __init__(self, camera: Camera, output_dir: Path, quality: int = JPEG_QUALITY) -> None:
        """Prepare to record the given camera into the given folder."""
        self.camera = camera
        self.output_dir = output_dir
        self.quality = quality
        self.sizes: list[int] = []

    def record(self, total_frames: int) -> int:
        """Capture and save total_frames pictures. Returns how many were saved.

        Pictures are read continuously and only kept when one is due. Skipping
        the read instead would let unread pictures build up inside the camera
        connection, and the recording would drift behind real time.
        """
        capture = self._open()
        if capture is None:
            print("Could not open " + self.camera.name, file=sys.stderr)
            return 0

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.sizes = []

        saved = 0
        kept_time = None
        started = time.monotonic()

        try:
            while saved < total_frames:
                received, image = capture.read()
                if not received or image is None:
                    print("\nCamera stopped sending pictures.", file=sys.stderr)
                    break

                now = time.monotonic()
                if not self._is_due(kept_time, now):
                    continue
                kept_time = now

                self.sizes.append(self._save(image, saved))
                saved = saved + 1

                if saved % PROGRESS_EVERY == 0 or saved == total_frames:
                    self._report(saved, total_frames, now - started)
        except KeyboardInterrupt:
            print("\nStopped early at " + str(saved) + " frames.")
        finally:
            capture.release()

        print()
        return saved

    def _open(self) -> cv2.VideoCapture | None:
        """Open the camera, asking for MJPG so the frame rate is not throttled."""
        camera = self.camera

        if camera.is_ip_camera():
            capture = cv2.VideoCapture(str(camera.address), cv2.CAP_FFMPEG)
        else:
            capture = cv2.VideoCapture(int(camera.address), cv2.CAP_V4L2)
            capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
            if camera.width and camera.height:
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, camera.width)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, camera.height)

        if not capture.isOpened():
            capture.release()
            return None

        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return capture

    def _is_due(self, kept_time: float | None, now: float) -> bool:
        """Return True when enough time has passed to keep another picture."""
        if self.camera.fps <= 0:
            return True
        if kept_time is None:
            return True

        wanted_gap = 1.0 / self.camera.fps
        return (now - kept_time) >= wanted_gap * RATE_TOLERANCE

    def _save(self, image: np.ndarray, index: int) -> int:
        """Write one picture as a numbered JPEG and return how many bytes it took."""
        path = self.output_dir / ("frame_{:05d}.jpg".format(index))
        return save_jpeg(image, path, self.quality)

    def _report(self, saved: int, total: int, elapsed: float) -> None:
        """Print progress on one line, with an estimate of the time remaining."""
        rate = saved / elapsed if elapsed > 0 else 0.0
        remaining = (total - saved) / rate if rate > 0 else 0.0
        message = "  {}/{} frames   {:.1f} fps   {:.0f}s left".format(
            saved, total, rate, remaining
        )
        # \r returns to the start of the line so progress overwrites itself.
        print(message.ljust(60), end="\r", flush=True)

    def summary(self) -> str:
        """Describe the sizes of the saved frames, for the paper's payload table."""
        return describe_sizes(self.sizes)


class RecordingStatus:
    """A snapshot of how a recording is going, for the window to display."""

    def __init__(
        self,
        running: bool,
        saved: int,
        elapsed: float,
        remaining: float,
        folder: Path,
        summary: str,
    ) -> None:
        """Record the state of one recording at one moment."""
        self.running = running
        self.saved = saved
        self.elapsed = elapsed
        self.remaining = remaining
        self.folder = folder
        self.summary = summary

    def clock(self) -> str:
        """Return the elapsed time as m:ss, for the button area."""
        minutes = int(self.elapsed // 60)
        seconds = int(self.elapsed % 60)
        return "{}:{:02d}".format(minutes, seconds)


class StreamRecorder:
    """Saves pictures from a camera that is already running, in the background.

    The viewer's Stream is already reading the camera, so this takes its
    pictures rather than opening the camera a second time - two programs reading
    one webcam usually fails, and a second RTSP session doubles the network load.

    Recording stops when stop() is called or when the time limit is reached,
    whichever happens first.
    """

    def __init__(
        self,
        stream: Stream,
        output_dir: Path,
        duration_seconds: float,
        quality: int = JPEG_QUALITY,
    ) -> None:
        """Prepare to record the given stream, without starting yet."""
        self.stream = stream
        self.output_dir = output_dir
        self.duration_seconds = duration_seconds
        self.quality = quality

        self._lock = threading.Lock()
        self._sizes: list[int] = []
        self._started_at = 0.0
        self._finished_at = 0.0
        self._running = False
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Begin recording. The clock starts now."""
        if self._running:
            return

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._stop.clear()
        self._sizes = []
        self._started_at = time.monotonic()
        self._finished_at = 0.0
        self._running = True

        self._thread = threading.Thread(target=self._run, name="recorder", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        """Stop recording early. Safe to call when nothing is running."""
        self._stop.set()

    def status(self) -> RecordingStatus:
        """Return how the recording is going, without blocking the window."""
        with self._lock:
            saved = len(self._sizes)
            sizes = list(self._sizes)
            running = self._running
            started = self._started_at
            finished = self._finished_at

        if started == 0.0:
            elapsed = 0.0
        elif running:
            elapsed = time.monotonic() - started
        else:
            elapsed = finished - started

        remaining = self.duration_seconds - elapsed
        if remaining < 0:
            remaining = 0.0

        return RecordingStatus(
            running, saved, elapsed, remaining, self.output_dir, describe_sizes(sizes)
        )

    def _run(self) -> None:
        """Background worker: save each new picture until the time runs out."""
        last_sequence = -1

        try:
            while not self._stop.is_set():
                if time.monotonic() - self._started_at >= self.duration_seconds:
                    break

                frame = self.stream.read()

                # The sequence number tells a fresh picture from the previous
                # one being handed out again, so nothing is saved twice.
                if frame.image is None or frame.sequence == last_sequence:
                    # Nothing new yet. A short pause keeps this thread from
                    # spinning and stealing time from the cameras.
                    time.sleep(0.01)
                    continue

                last_sequence = frame.sequence

                with self._lock:
                    index = len(self._sizes)

                path = self.output_dir / ("frame_{:05d}.jpg".format(index))
                written = save_jpeg(frame.image, path, self.quality)

                with self._lock:
                    self._sizes.append(written)
        finally:
            with self._lock:
                self._running = False
                self._finished_at = time.monotonic()


class PrivacyCheck:
    """Looks through saved frames for faces, so none reach a shared corpus."""

    def __init__(self, min_confidence: float) -> None:
        """Load a detector set to the same sensitivity the viewer uses."""
        self.detector = FaceDetector(min_confidence=min_confidence)

    def scan(self, folder: Path) -> list[Path]:
        """Return every saved frame that contains a face."""
        found = []
        frames = sorted(folder.glob("frame_*.jpg"))

        for position, path in enumerate(frames):
            image = cv2.imread(str(path))
            if image is None:
                continue
            if self.detector.detect(image):
                found.append(path)

            if position % PROGRESS_EVERY == 0:
                message = "  checking {}/{} ...".format(position, len(frames))
                print(message.ljust(60), end="\r", flush=True)

        print(" ".ljust(60), end="\r")
        return found


def pick_camera(cameras: list[Camera], choice: str) -> Camera | None:
    """Return the camera the user asked for by short name."""
    wanted = {"ipcam": 0, "webcam1": 1, "webcam2": 2}
    if choice not in wanted:
        return None

    position = wanted[choice]
    if position >= len(cameras):
        return None
    return cameras[position]


def record_all_cameras(config: Config, minutes: float, fps: int, quality: int) -> Path | None:
    """Record every configured camera at once, unattended, into one folder.

    This is the reliable way to run a long recording: there is no window to
    close by accident, so nothing can cut the session short. Each camera writes
    into its own subfolder of one dated session folder.

    Returns the session folder, or None when no camera could be reached.
    """
    cameras = []
    for camera in config.cameras():
        # Record at the rate asked for here, not the viewer's rate from .env.
        cameras.append(
            Camera(
                name=camera.name,
                kind=camera.kind,
                address=camera.address,
                width=camera.width,
                height=camera.height,
                fps=fps,
            )
        )

    streams = []
    for camera in cameras:
        stream = Stream(camera)
        stream.start()
        streams.append(stream)

    print("Waiting for the cameras to come up ...")
    time.sleep(8)

    ready = []
    for stream in streams:
        frame = stream.read()
        if frame.image is None:
            print("  skipping " + stream.camera.name + " - not sending pictures")
        else:
            print("  ready: " + stream.camera.name + "  " + frame.detail)
            ready.append(stream)

    if not ready:
        for stream in streams:
            stream.stop()
        return None

    # A fixed stamp, so every camera in this session shares one folder.
    stamp = time.strftime("%Y%m%d-%H%M%S")
    seconds = minutes * 60

    recorders = []
    for stream in ready:
        recorder = StreamRecorder(stream, group_folder(stream.camera.name, stamp), seconds, quality)
        recorder.start()
        recorders.append(recorder)

    print(
        "\nRecording {} camera(s) for {:.0f} minutes -> payloads/{}/".format(
            len(ready), minutes, stamp
        )
    )
    print("  press Ctrl+C to stop early\n")

    try:
        while True:
            running = False
            saved = 0
            for recorder in recorders:
                status = recorder.status()
                if status.running:
                    running = True
                saved = saved + status.saved

            if not running:
                break

            first = recorders[0].status()
            message = "  {}  {} frames   {:.0f}s left".format(first.clock(), saved, first.remaining)
            print(message.ljust(60), end="\r", flush=True)
            time.sleep(1.0)
    except KeyboardInterrupt:
        print("\nStopping early ...")
        for recorder in recorders:
            recorder.stop()
        while any(r.status().running for r in recorders):
            time.sleep(0.2)

    print()
    for recorder in recorders:
        status = recorder.status()
        print("  " + status.folder.name + ": " + status.summary)

    for stream in streams:
        stream.stop()

    return PAYLOAD_ROOT / stamp


def parse_arguments() -> argparse.Namespace:
    """Read the command-line options."""
    parser = argparse.ArgumentParser(
        description="Record real camera frames as JPEG benchmark payloads."
    )
    parser.add_argument("--minutes", type=float, default=10.0, help="how long to record")
    parser.add_argument("--fps", type=int, default=5, help="pictures per second to keep")
    parser.add_argument(
        "--camera",
        default="ipcam",
        choices=["ipcam", "webcam1", "webcam2"],
        help="which camera to record",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="record every camera at once, into one dated session folder",
    )
    parser.add_argument("--output", default="payloads", help="folder to write frames into")
    parser.add_argument("--quality", type=int, default=JPEG_QUALITY, help="JPEG quality")
    parser.add_argument(
        "--no-check",
        action="store_true",
        help="skip the face sweep once recording finishes",
    )
    return parser.parse_args()


def main() -> int:
    """Record the frames, then report their sizes and check them for faces."""
    arguments = parse_arguments()
    config = Config()

    if arguments.all:
        session = record_all_cameras(
            config, arguments.minutes, arguments.fps, arguments.quality
        )
        if session is None:
            print("No camera could be reached.", file=sys.stderr)
            return 1

        if arguments.no_check:
            return 0

        print("\nChecking frames for faces ...")
        checker = PrivacyCheck(config.face_min_confidence)
        for folder in sorted(session.iterdir()):
            if not folder.is_dir():
                continue
            with_faces = checker.scan(folder)
            if with_faces:
                print("  {}: FACES in {} frames - do not publish".format(folder.name, len(with_faces)))
            else:
                print("  {}: clean".format(folder.name))
        return 0

    camera = pick_camera(config.cameras(), arguments.camera)
    if camera is None:
        print("Camera '" + arguments.camera + "' is not configured in .env", file=sys.stderr)
        return 1

    # Record at the rate asked for here, not the one .env uses for the viewer.
    camera = Camera(
        name=camera.name,
        kind=camera.kind,
        address=camera.address,
        width=camera.width,
        height=camera.height,
        fps=arguments.fps,
    )

    total_frames = int(arguments.minutes * 60 * arguments.fps)
    output_dir = Path(arguments.output)
    if not output_dir.is_absolute():
        output_dir = HERE / output_dir

    print("Recording from " + camera.name)
    print(
        "  {:.0f} minutes at {} fps = {} frames -> {}/".format(
            arguments.minutes, arguments.fps, total_frames, output_dir.name
        )
    )
    print("  press Ctrl+C to stop early\n")

    recorder = FrameRecorder(camera, output_dir, arguments.quality)
    saved = recorder.record(total_frames)
    if saved == 0:
        return 1

    print(recorder.summary())

    if arguments.no_check:
        return 0

    print("\nChecking frames for faces ...")
    checker = PrivacyCheck(config.face_min_confidence)
    with_faces = checker.scan(output_dir)

    if not with_faces:
        print("  no faces found - this corpus is safe to share")
    else:
        print("  FACES FOUND in " + str(len(with_faces)) + " of " + str(saved) + " frames.")
        print("  Do not publish this corpus. First few:")
        for path in with_faces[:5]:
            print("    " + path.name)

    return 0


if __name__ == "__main__":
    sys.exit(main())
