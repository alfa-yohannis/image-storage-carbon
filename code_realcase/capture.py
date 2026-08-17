"""Reads pictures from the cameras, one background worker per camera.

Why this module exists
----------------------
A camera hands us one picture (a "frame") at a time, and waiting for the next one
takes a moment. If we waited inside the window's own loop, the whole window would
freeze between pictures: buttons would not respond and the video would stutter.

The solution is a *thread*: a second line of work running at the same time as the
window. Each camera gets its own thread that reads pictures non-stop and keeps
only the newest one. The window then simply asks "what is the newest picture?"
whenever it redraws, and never has to wait.

Reading non-stop matters for network cameras too. If we read only now and then,
unread pictures pile up inside the camera connection and the video slowly falls
behind real time - by seconds, after a while.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

import cv2
import numpy as np

from config import Camera
from faces import Face, FaceFinder

# Faces are looked for a few times a second rather than on every picture.
# Searching is the most expensive thing here, and a face does not move far in
# a fifth of a second, so the last known boxes stay accurate between searches.
DETECT_INTERVAL = 0.2

# How long to wait before trying a camera again after it fails. The wait doubles
# each time, up to the maximum, so a camera that is simply switched off does not
# cause constant retries.
FIRST_RETRY_DELAY = 1.0
MAX_RETRY_DELAY = 10.0

# When limiting the rate, accept a picture that arrives slightly early. Without
# this, a camera sending 30 per second could never hit a 15 target: two gaps of
# 33 ms fall 1 ms short of 66.7 ms, so every second picture would be refused and
# the result would be 10 instead of 15.
RATE_TOLERANCE = 0.95

# The four situations a camera can be in. Using named values instead of loose
# text means a typo becomes an error the editor can catch.
CONNECTING = "connecting"
LIVE = "live"
DISCONNECTED = "disconnected"
STOPPED = "stopped"


@dataclass(frozen=True)
class Frame:
    """One snapshot of a camera's situation, handed to the window when it redraws.

    Fields:
        image:  the picture itself, or None if there is nothing to show yet.
        status: one of CONNECTING, LIVE, DISCONNECTED or STOPPED.
        fps:    how many pictures per second are arriving.
        detail: a short extra note, such as the picture size or an error.
        faces:  the faces found in this picture, ready to be drawn.
        sequence: counts up by one for every new picture. A reader can compare
                it with the number it saw last time to tell a fresh picture from
                the previous one being served again. The recorder relies on this
                so it never saves the same picture twice.
    """

    image: np.ndarray | None
    status: str
    fps: float
    detail: str = ""
    faces: tuple[Face, ...] = ()
    sequence: int = 0


class Stream:
    """Reads one camera in the background and keeps its newest picture.

    Two threads touch this object: the background worker that stores new pictures
    and the window that reads them. To stop them clashing, every access goes
    through a *lock* - a token that only one thread may hold at a time. The
    "with self._lock:" lines below take the token and give it back automatically.
    """

    def __init__(self, camera: Camera, finder: FaceFinder | None = None) -> None:
        """Get ready to read the given camera, but do not open it yet.

        Passing a FaceFinder switches face detection on for this camera. The
        search happens on this camera's own thread, so a slow search delays only
        this camera and never the window.
        """
        self.camera = camera
        self._finder = finder

        # The shared box holding the latest picture and status. Never read or
        # write these without holding the lock.
        self._lock = threading.Lock()
        self._image: np.ndarray | None = None
        self._status: str = CONNECTING
        self._detail: str = ""
        self._fps: float = 0.0
        self._faces: tuple[Face, ...] = ()
        self._sequence: int = 0

        # An Event is a flag both threads can see. We raise it to ask the worker
        # to finish.
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        """Start reading in the background. Calling it twice does nothing extra."""
        if self._thread is not None:
            return

        # daemon=True lets the program exit even if this thread is still running.
        self._thread = threading.Thread(
            target=self._run,
            name="stream:" + self.camera.name,
            daemon=True,
        )
        self._thread.start()

    def stop(self, timeout: float = 2.0) -> None:
        """Ask the worker to finish and wait briefly for it to release the camera."""
        self._stop.set()
        if self._thread is not None:
            # join() waits for the thread to end, but not forever: if the camera
            # is stuck, we give up after timeout seconds rather than hang.
            self._thread.join(timeout)
            self._thread = None
        self._publish(status=STOPPED)

    def read(self) -> Frame:
        """Return the newest picture and status. Returns at once, never waits."""
        with self._lock:
            return Frame(
                self._image,
                self._status,
                self._fps,
                self._detail,
                self._faces,
                self._sequence,
            )

    def _run(self) -> None:
        """The background worker: keep a camera open and store every picture.

        This method runs on the worker thread, not the main one. It loops until
        stop() is called.
        """
        capture = None
        delay = FIRST_RETRY_DELAY
        previous_time = None
        kept_time = None
        detect_time = None
        faces: tuple[Face, ...] = ()

        try:
            while not self._stop.is_set():
                # Step 1: make sure the camera is open.
                if capture is None:
                    self._publish(status=CONNECTING)
                    capture = self._open()

                if capture is None:
                    delay = self._wait_before_retry(delay)
                    if delay is None:
                        break  # stop() was called while we were waiting
                    continue

                # Step 2: ask for the next picture.
                received, image = capture.read()
                if not received or image is None:
                    # The camera was unplugged or the network dropped. Let it go
                    # and the next loop will try to open it again.
                    capture.release()
                    capture = None
                    self._publish(status=DISCONNECTED, detail="stream ended")
                    continue

                # A successful read means the camera is healthy again.
                delay = FIRST_RETRY_DELAY
                now = time.monotonic()

                # Step 3: keep this picture only if it is due.
                #
                # We always *read* every picture, even the ones we throw away.
                # Skipping the read instead would let unread pictures pile up
                # inside the camera connection, and the video would fall behind.
                if not self._is_due(kept_time, now):
                    continue

                # Step 4: look for faces, but only a few times a second.
                # Between searches the previous boxes are reused, which keeps
                # the marker visible without paying the cost every picture.
                if self._finder is not None and self._is_detect_due(detect_time, now):
                    faces = tuple(self._finder.find(image))
                    detect_time = now

                # Step 5: measure the rate of the pictures we keep, and publish.
                self._update_fps(kept_time, now)
                kept_time = now
                previous_time = now

                height, width = image.shape[:2]
                size_text = str(width) + "x" + str(height)
                self._publish(image=image, status=LIVE, detail=size_text, faces=faces)
        finally:
            # Runs whatever happens, so the camera is always handed back to the
            # system even if something above raises an error.
            if capture is not None:
                capture.release()

    def _open(self) -> cv2.VideoCapture | None:
        """Open the camera and return it, or return None if it is unavailable."""
        camera = self.camera

        if camera.is_ip_camera():
            # A network camera is opened by its rtsp:// address.
            capture = cv2.VideoCapture(str(camera.address), cv2.CAP_FFMPEG)
        else:
            # A webcam is opened by its number: 0 means /dev/video0.
            capture = cv2.VideoCapture(int(camera.address), cv2.CAP_V4L2)

            # By default many webcams send raw, uncompressed pictures, and the
            # USB cable cannot carry more than about 10 per second at 720p.
            # Asking for MJPG makes the camera compress each picture first, which
            # usually lifts the rate to 30. Must be set before the size below.
            capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))

            if camera.width and camera.height:
                capture.set(cv2.CAP_PROP_FRAME_WIDTH, camera.width)
                capture.set(cv2.CAP_PROP_FRAME_HEIGHT, camera.height)

        if not capture.isOpened():
            capture.release()
            return None

        # Ask the camera to keep just one picture waiting, so what we read is the
        # newest one rather than the oldest in a queue. Not every camera obeys
        # this, which is why the worker also reads non-stop.
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return capture

    def _wait_before_retry(self, delay: float) -> float | None:
        """Report the camera as unreachable, pause, then return the next delay.

        Returns None if stop() was called during the pause, telling the worker
        to finish.
        """
        self._publish(
            status=DISCONNECTED,
            detail="cannot open - retrying in " + str(int(delay)) + "s",
        )

        # Waiting on the stop flag rather than sleeping means closing the window
        # takes effect immediately instead of after the full delay.
        if self._stop.wait(delay):
            return None

        return min(delay * 2, MAX_RETRY_DELAY)

    def _is_due(self, kept_time: float | None, now: float) -> bool:
        """Return True when the next picture should be kept.

        Cameras ignore a request to run slower, so a chosen rate has to be
        applied here: read everything, keep only what is due. A camera with
        fps set to 0 has no limit and every picture is kept.
        """
        if self.camera.fps <= 0:
            return True
        if kept_time is None:
            return True  # always keep the first one

        wanted_gap = 1.0 / self.camera.fps
        return (now - kept_time) >= wanted_gap * RATE_TOLERANCE

    def _is_detect_due(self, detect_time: float | None, now: float) -> bool:
        """Return True when it is time to search for faces again."""
        if detect_time is None:
            return True
        return (now - detect_time) >= DETECT_INTERVAL

    def _update_fps(self, previous_time: float | None, now: float) -> None:
        """Work out how many pictures per second are arriving."""
        if previous_time is None:
            return  # first picture: no gap to measure yet

        elapsed = now - previous_time
        if elapsed <= 0:
            return

        instant = 1.0 / elapsed
        with self._lock:
            if self._fps == 0:
                self._fps = instant
            else:
                # Blend mostly the old value with a little of the new one, so the
                # number on screen drifts smoothly instead of jumping about.
                self._fps = self._fps * 0.9 + instant * 0.1

    def _publish(
        self,
        image: np.ndarray | None = None,
        status: str | None = None,
        detail: str | None = None,
        faces: tuple[Face, ...] | None = None,
    ) -> None:
        """Store new values in the shared box that read() serves to the window.

        Only the values passed in are changed; anything left out keeps its
        current value.
        """
        with self._lock:
            if image is not None:
                self._image = image
                self._sequence = self._sequence + 1
            if status is not None:
                self._status = status
                if status != LIVE:
                    self._fps = 0.0
                    self._faces = ()
            if detail is not None:
                self._detail = detail
            if faces is not None:
                self._faces = faces
