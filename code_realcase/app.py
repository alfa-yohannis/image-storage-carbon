#!/usr/bin/env python3
"""A live viewer for three cameras: one Tapo IP camera and two USB webcams.

The window is a 2x2 grid. Three cells show video and the fourth lists the
cameras that were found in the .env file.

How the pieces fit together:
    config.py   reads .env and produces Camera objects
    capture.py  reads each camera in the background (one Stream per camera)
    app.py      draws the window and shows the newest picture from each Stream

The first time you run it, this script builds a local .venv folder, installs the
packages listed in requirements.txt, and restarts itself inside that folder, so
there is nothing to set up by hand.

Keys:
    s        save a picture from every working camera into snapshots/
    f        switch fullscreen on or off
    q / Esc  quit

Examples:
    python app.py                  # show all three cameras
    python app.py --only webcam    # show the webcams only
    python app.py --list           # print the configured cameras and exit
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


from bootstrap import ensure_venv  # noqa: E402

ensure_venv("app.py")

# These packages live inside .venv, so they can only be imported after
# ensure_venv() has restarted us in there.
import shutil
import tkinter as tk
from datetime import datetime
from tkinter import messagebox, ttk

import cv2
import numpy as np
from PIL import Image, ImageTk

from capture import DISCONNECTED, LIVE, Frame, Stream
from config import Camera, Config
from faces import FaceFinder
from record import StreamRecorder, group_folder, session_folder

# The extra dropdown entry that records every camera at once, rather than one.
ALL_CAMERAS = "All cameras"


class Theme:
    """The colours used throughout the window, kept in one place to edit easily."""

    PAGE = "#14161a"
    TILE = "#1c1f26"
    VIDEO = "#0b0d10"
    TEXT = "#e6e8ec"
    FAINT = "#8b93a1"

    # A colour for each camera status, so the state is readable at a glance.
    STATUS = {
        LIVE: "#46c46e",
        "connecting": "#e0b341",
        DISCONNECTED: "#e0574a",
        "stopped": "#8b93a1",
    }

    # The face marker. OpenCV takes colours as Blue, Green, Red - not RGB - so
    # pure green is (0, 255, 0). These are drawn before the picture is converted
    # to RGB, which is why they use OpenCV's order.
    FACE_BOX = (0, 255, 0)
    FACE_TEXT = (0, 255, 0)


class CameraView(ttk.Frame):
    """One tile of the grid: a title line on top and the video underneath.

    This class extends ttk.Frame, which means a CameraView *is* a frame and can
    be placed in the window like any other widget.
    """

    def __init__(self, parent: tk.Widget, camera: Camera) -> None:
        """Build the tile for one camera."""
        super().__init__(parent, padding=6, style="Tile.TFrame")
        self.camera = camera

        # Tk throws away a picture that no variable refers to, and the video
        # would flicker or vanish. Keeping it here prevents that.
        self._photo: ImageTk.PhotoImage | None = None

        # The most recent picture, kept so the snapshot key has something to save.
        self._last_image: np.ndarray | None = None

        header = ttk.Frame(self, style="Tile.TFrame")
        header.pack(fill="x")
        ttk.Label(header, text=camera.name, style="Title.TLabel").pack(side="left")

        self.status_label = ttk.Label(header, text="connecting", style="Status.TLabel")
        self.status_label.pack(side="right")

        self.video_label = tk.Label(
            self,
            bg=Theme.VIDEO,
            fg=Theme.FAINT,
            text="waiting for video...",
        )
        self.video_label.pack(fill="both", expand=True, pady=(6, 0))

    def show(self, frame: Frame) -> None:
        """Draw the given Frame: update the status line, then the picture."""
        self._show_status(frame)
        self._show_image(frame)

    def _show_status(self, frame: Frame) -> None:
        """Write the status, frame rate and picture size along the title line."""
        parts = [frame.status]
        if frame.status == LIVE:
            parts.append("{:.1f} fps".format(frame.fps))
        if frame.detail:
            parts.append(frame.detail)

        colour = Theme.STATUS.get(frame.status, Theme.FAINT)
        self.status_label.configure(text="   ".join(parts), foreground=colour)

    def _show_image(self, frame: Frame) -> None:
        """Scale the picture to the tile and display it."""
        if frame.image is None:
            self.video_label.configure(image="", text="no signal")
            self._photo = None
            return

        width = self.video_label.winfo_width()
        height = self.video_label.winfo_height()

        # Just after the window opens, Tk has not decided how big the tile is
        # yet and reports 1 pixel. Skip this round and draw on the next one.
        if width < 16 or height < 16:
            return

        picture = self._fit(frame.image, width, height)

        # The face boxes were worked out on the full-size picture, so they must
        # be shrunk by the same amount before being drawn on this smaller copy.
        shrink = picture.shape[1] / frame.image.shape[1]
        self._draw_faces(picture, frame.faces, shrink)

        # OpenCV stores colours as Blue-Green-Red, while the rest of the world
        # uses Red-Green-Blue. Without this swap everyone looks blue.
        picture = cv2.cvtColor(picture, cv2.COLOR_BGR2RGB)

        self._photo = ImageTk.PhotoImage(Image.fromarray(picture))
        self._last_image = frame.image
        self.video_label.configure(image=self._photo, text="")

    def _draw_faces(self, picture: np.ndarray, faces, shrink: float) -> None:
        """Draw a green box around every face, with its label above it.

        The picture is changed in place. It is the shrunken display copy, never
        the original, so a saved snapshot stays clean of drawings.
        """
        for face in faces:
            left = int(face.x * shrink)
            top = int(face.y * shrink)
            right = int((face.x + face.width) * shrink)
            bottom = int((face.y + face.height) * shrink)

            cv2.rectangle(picture, (left, top), (right, bottom), Theme.FACE_BOX, 2)

            # Put the label just above the box, or just below it when the face
            # is at the very top of the picture and there is no room above.
            text_y = top - 8
            if text_y < 14:
                text_y = bottom + 18

            cv2.putText(
                picture,
                face.label(),
                (left, text_y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                Theme.FACE_TEXT,
                1,
                cv2.LINE_AA,
            )

    def _fit(self, image: np.ndarray, box_width: int, box_height: int) -> np.ndarray:
        """Shrink the picture to fit the tile while keeping its shape.

        Using the smaller of the two scale factors means the picture always fits
        inside the tile, and people do not end up stretched.
        """
        image_height, image_width = image.shape[:2]
        scale = min(box_width / image_width, box_height / image_height)

        new_width = max(1, int(image_width * scale))
        new_height = max(1, int(image_height * scale))

        # INTER_AREA gives the best result when making a picture smaller.
        return cv2.resize(image, (new_width, new_height), interpolation=cv2.INTER_AREA)

    def save_image(self, folder: Path, stamp: str) -> Path | None:
        """Save the latest picture as a JPEG and return its path, or None."""
        if self._last_image is None:
            return None

        # Turn the camera name into something safe for a filename.
        safe_name = ""
        for character in self.camera.name:
            if character.isalnum():
                safe_name = safe_name + character
            else:
                safe_name = safe_name + "_"

        path = folder / (stamp + "_" + safe_name.strip("_") + ".jpg")
        cv2.imwrite(str(path), self._last_image, [cv2.IMWRITE_JPEG_QUALITY, 95])
        return path


class InfoPanel(ttk.Frame):
    """The fourth cell of the grid: the recording controls and the camera list.

    The panel owns the Start/Stop button and the clock, but not the recording
    itself. Pressing the button calls back into the window, which owns the
    recorder - keeping the widget concerned only with what is on screen.
    """

    def __init__(
        self,
        parent: tk.Widget,
        cameras: list[Camera],
        config: Config,
        on_record: object,
        on_clear: object,
    ) -> None:
        """Build the panel. The two callbacks fire when the buttons are pressed."""
        super().__init__(parent, padding=10, style="Tile.TFrame")
        self.cameras = cameras

        ttk.Label(self, text="Record payload frames", style="Title.TLabel").pack(anchor="w")

        # Which camera to record from. "All cameras" sits first because a
        # session that captures everything at once is the common case.
        choices = [ALL_CAMERAS]
        for camera in cameras:
            choices.append(camera.name)

        self.camera_choice = tk.StringVar(value=ALL_CAMERAS)
        chooser = ttk.Combobox(
            self,
            textvariable=self.camera_choice,
            values=choices,
            state="readonly",
            width=30,
        )
        chooser.pack(anchor="w", pady=(6, 0))

        row = ttk.Frame(self, style="Tile.TFrame")
        row.pack(anchor="w", fill="x", pady=(8, 0))

        self.record_button = ttk.Button(row, text="Start recording", command=on_record)
        self.record_button.pack(side="left")

        self.clock_label = ttk.Label(row, text="0:00", style="Clock.TLabel")
        self.clock_label.pack(side="left", padx=(10, 0))

        self.clear_button = ttk.Button(row, text="Clear payloads", command=on_clear)
        self.clear_button.pack(side="right")

        self.record_status = ttk.Label(
            self,
            text="{:.0f} min at {} fps".format(config.record_minutes, config.record_fps),
            style="Info.TLabel",
        )
        self.record_status.pack(anchor="w", pady=(6, 0))

        ttk.Label(self, text="\nCameras", style="Title.TLabel").pack(anchor="w")
        for camera in cameras:
            # safe_address() hides the password, so this is safe to show.
            text = "- " + camera.safe_address()
            ttk.Label(self, text=text, style="Info.TLabel").pack(anchor="w", pady=(2, 0))

        summary = "\nsaves to    {}/".format(config.payload_dir.name)
        ttk.Label(self, text=summary, style="Info.TLabel").pack(anchor="w")

    def wants_all_cameras(self) -> bool:
        """True when the dropdown is set to record every camera at once."""
        return self.camera_choice.get() == ALL_CAMERAS

    def selected_index(self) -> int:
        """Return the position of the chosen camera in the camera list."""
        chosen = self.camera_choice.get()
        for position, camera in enumerate(self.cameras):
            if camera.name == chosen:
                return position
        return 0

    def show_recording(self, running: bool, clock: str, message: str) -> None:
        """Update the button, the clock and the line beneath them."""
        if running:
            self.record_button.configure(text="Stop recording")
            # Deleting frames while they are being written would be a mess.
            self.clear_button.configure(state="disabled")
        else:
            self.record_button.configure(text="Start recording")
            self.clear_button.configure(state="normal")

        self.clock_label.configure(text=clock)
        self.record_status.configure(text=message)


class App(tk.Tk):
    """The main window: a 2x2 grid of camera tiles plus the info panel."""

    def __init__(self, config: Config, cameras: list[Camera]) -> None:
        """Build the window, start one background Stream per camera, and run."""
        super().__init__()
        self.config_data = config
        self.is_fullscreen = False

        self.title("Camera Wall - IP camera and webcams")
        self.configure(bg=Theme.PAGE)
        self.minsize(720, 480)
        self._center_window(1280, 760)
        self._apply_styles()

        # One Stream and one CameraView per camera, kept in matching order so
        # views[i] always shows streams[i].
        self.streams: list[Stream] = []
        self.views: list[CameraView] = []

        # One finder per camera - see _make_finders for why they cannot be shared.
        self.finders = self._make_finders(len(cameras))

        # One recorder per camera being recorded. Empty when nothing is
        # recording; holds a single entry for one camera, or one per camera when
        # the whole set is being captured together.
        self.recorders: list[StreamRecorder] = []

        grid = ttk.Frame(self, padding=8, style="Page.TFrame")
        grid.pack(fill="both", expand=True)

        # weight=1 lets both rows and columns share the space as the window
        # resizes; uniform keeps every cell the same size as its neighbours.
        for position in (0, 1):
            grid.rowconfigure(position, weight=1, uniform="row")
            grid.columnconfigure(position, weight=1, uniform="column")

        self._build_tiles(grid, cameras)
        self._build_info(grid, cameras, len(cameras))

        self.status_bar = ttk.Label(self, text="", style="Footer.TLabel", anchor="w")
        self.status_bar.pack(fill="x", padx=12, pady=(0, 8))
        self.set_status(
            "records to " + str(self.config_data.payload_dir)
            + "     s = snapshot   f = fullscreen   q / Esc = quit"
        )

        self._bind_keys()

        for stream in self.streams:
            stream.start()

        self._refresh()

    def _make_finders(self, count: int) -> list[FaceFinder | None]:
        """Build one face finder per camera, or a list of None when switched off.

        They must not be shared. Before each search the model is told the size
        of the picture, which changes the model's own working buffers. Two
        cameras searching at the same time overwrite each other's buffers and
        OpenCV raises "buf.shape() == m.shape()". A separate finder per camera
        avoids this, and the detection model is only 228 KB.

        A missing model file should not stop the cameras from working, so the
        problem is reported and the app carries on without face marking.
        """
        finders: list[FaceFinder | None] = []

        if not self.config_data.face_detection:
            for _ in range(count):
                finders.append(None)
            return finders

        try:
            for _ in range(count):
                finders.append(
                    FaceFinder(
                        recognise=self.config_data.face_recognition,
                        min_confidence=self.config_data.face_min_confidence,
                    )
                )
        except FileNotFoundError as error:
            print("[faces] detection is off: " + str(error))
            finders = []
            for _ in range(count):
                finders.append(None)

        return finders

    def _build_tiles(self, grid: ttk.Frame, cameras: list[Camera]) -> None:
        """Create one Stream and one CameraView for each camera."""
        for position, camera in enumerate(cameras):
            self.streams.append(Stream(camera, self.finders[position]))

            view = CameraView(grid, camera)
            # Cell 0 goes top-left, 1 top-right, 2 bottom-left, 3 bottom-right.
            view.grid(row=position // 2, column=position % 2, sticky="nsew", padx=4, pady=4)
            self.views.append(view)

    def _build_info(self, grid: ttk.Frame, cameras: list[Camera], position: int) -> None:
        """Place the recording panel in the cell after the last camera tile."""
        self.info = InfoPanel(
            grid, cameras, self.config_data, self.on_record, self.on_clear
        )
        self.info.grid(row=position // 2, column=position % 2, sticky="nsew", padx=4, pady=4)

    def _bind_keys(self) -> None:
        """Connect the keyboard shortcuts and the window's close button."""
        self.bind("<Key-s>", self.on_snapshot)
        self.bind("<Key-f>", self.on_fullscreen)
        self.bind("<Key-q>", self.on_quit)
        self.bind("<Escape>", self.on_quit)
        self.protocol("WM_DELETE_WINDOW", self.on_quit)

    def _center_window(self, width: int, height: int) -> None:
        """Place a window of the given size in the middle of the screen.

        Tk positions windows with a geometry string shaped "WxH+X+Y", where X
        and Y are the distance from the left and top of the screen. Subtracting
        the window size from the screen size and halving it leaves an equal gap
        on each side, which puts the window in the centre.
        """
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        left = (screen_width - width) // 2
        top = (screen_height - height) // 2

        # A window larger than the screen would otherwise be pushed off the top
        # left corner, so never allow a negative position.
        left = max(0, left)
        top = max(0, top)

        self.geometry("{}x{}+{}+{}".format(width, height, left, top))

    def _apply_styles(self) -> None:
        """Describe how each kind of label and frame should look."""
        style = ttk.Style(self)
        style.theme_use("clam")
        style.configure("Page.TFrame", background=Theme.PAGE)
        style.configure("Tile.TFrame", background=Theme.TILE)
        style.configure(
            "Title.TLabel",
            background=Theme.TILE,
            foreground=Theme.TEXT,
            font=("TkDefaultFont", 10, "bold"),
        )
        style.configure(
            "Status.TLabel",
            background=Theme.TILE,
            foreground=Theme.FAINT,
            font=("TkFixedFont", 9),
        )
        style.configure(
            "Info.TLabel",
            background=Theme.TILE,
            foreground=Theme.FAINT,
            font=("TkFixedFont", 9),
            justify="left",
        )
        style.configure(
            "Footer.TLabel",
            background=Theme.PAGE,
            foreground=Theme.FAINT,
            font=("TkFixedFont", 9),
        )
        style.configure(
            "Clock.TLabel",
            background=Theme.TILE,
            foreground=Theme.TEXT,
            font=("TkFixedFont", 13, "bold"),
        )

    def _refresh(self) -> None:
        """Redraw every tile, then ask Tk to call this again shortly.

        after() schedules the next call without blocking, which is how a Tk
        program repeats work while staying responsive to clicks and keys.
        """
        for view, stream in zip(self.views, self.streams):
            view.show(stream.read())

        self._refresh_recording()

        delay_ms = max(1, 1000 // self.config_data.target_fps)
        self.after(delay_ms, self._refresh)

    def _refresh_recording(self) -> None:
        """Update the clock and button while a recording is under way.

        Recorders run on their own threads; this only reads their progress,
        which is why the window keeps responding during a ten-minute recording.
        """
        if not self.recorders:
            return

        statuses = []
        for recorder in self.recorders:
            statuses.append(recorder.status())

        still_running = False
        total_saved = 0
        for status in statuses:
            if status.running:
                still_running = True
            total_saved = total_saved + status.saved

        # Every recorder starts together, so any clock represents the session.
        clock = statuses[0].clock()

        if still_running:
            message = "{} frames from {} camera(s)   {:.0f}s left".format(
                total_saved, len(statuses), statuses[0].remaining
            )
            self.info.show_recording(True, clock, message)
            return

        # All recorders have stopped, at the time limit or on request.
        self.info.show_recording(False, clock, "{} frames saved".format(total_saved))
        self._report_finished(statuses)
        self.recorders = []

    def _report_finished(self, statuses: list) -> None:
        """Print each camera's result and point the status bar at the folder."""
        for status in statuses:
            print("[record] " + status.folder.name + ": " + status.summary)

        if len(statuses) == 1:
            self.set_status("saved to " + str(statuses[0].folder))
        else:
            # Every camera wrote into the same dated folder, one level up.
            self.set_status("saved to " + str(statuses[0].folder.parent))

    def on_record(self) -> None:
        """Start recording, or stop whatever is already recording.

        The button does both jobs, so which one happens depends on whether any
        recorder is currently active.
        """
        if self.recorders:
            for recorder in self.recorders:
                recorder.stop()
            self.set_status("stopping ...")
            return

        wanted = self._chosen_streams()
        ready = []
        for stream in wanted:
            # A camera that is not delivering would produce an empty folder.
            if stream.read().image is not None:
                ready.append(stream)

        if not ready:
            self.set_status("cannot record - no camera is sending pictures")
            return

        self._start_recording(ready, record_all=len(wanted) > 1)

    def on_clear(self) -> None:
        """Delete every recorded frame, after asking for confirmation.

        Recordings are slow to make and impossible to recover, so this always
        asks first and states exactly how much is about to go.
        """
        if self.recorders:
            self.set_status("cannot clear while recording")
            return

        folder = self.config_data.payload_dir
        sessions, frames, megabytes = self._measure_payloads(folder)

        if frames == 0:
            self.set_status("nothing to clear - " + folder.name + "/ is already empty")
            return

        question = (
            "Delete every recorded frame?\n\n"
            "{} session(s), {} frames, {:.0f} MB\n\n"
            "This cannot be undone."
        ).format(sessions, frames, megabytes)

        if not messagebox.askyesno("Clear payloads", question, icon="warning"):
            self.set_status("clear cancelled - nothing was deleted")
            return

        removed = self._delete_payloads(folder)
        self.set_status("cleared {} session(s) from {}/".format(removed, folder.name))
        self.info.show_recording(False, "0:00", "no recordings")

    def _measure_payloads(self, folder: Path) -> tuple[int, int, float]:
        """Count the sessions, frames and megabytes currently recorded."""
        if not folder.is_dir():
            return 0, 0, 0.0

        sessions = 0
        frames = 0
        total_bytes = 0

        for entry in folder.iterdir():
            if not entry.is_dir():
                continue
            sessions = sessions + 1
            # rglob reaches frames one level down too, for multi-camera sessions.
            for image in entry.rglob("frame_*.jpg"):
                frames = frames + 1
                total_bytes = total_bytes + image.stat().st_size

        return sessions, frames, total_bytes / 1_000_000

    def _delete_payloads(self, folder: Path) -> int:
        """Remove every session folder. Returns how many were removed.

        Only folders directly inside the payload folder are touched, so a
        mistake here cannot reach anything else on the disk.
        """
        if not folder.is_dir():
            return 0

        removed = 0
        for entry in folder.iterdir():
            if entry.is_dir():
                shutil.rmtree(entry, ignore_errors=True)
                removed = removed + 1

        return removed

    def _chosen_streams(self) -> list[Stream]:
        """Return the streams the dropdown is asking to record."""
        if self.info.wants_all_cameras():
            return list(self.streams)
        return [self.streams[self.info.selected_index()]]

    def _start_recording(self, streams: list[Stream], record_all: bool) -> None:
        """Begin recording every given stream, all sharing one start time."""
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        seconds = self.config_data.record_minutes * 60

        for stream in streams:
            # Recording several cameras groups them under one dated folder;
            # a single camera gets a dated folder of its own.
            if record_all:
                folder = group_folder(stream.camera.name, stamp)
            else:
                folder = session_folder(stream.camera.name, stamp)

            recorder = StreamRecorder(stream, folder, seconds)
            recorder.start()
            self.recorders.append(recorder)

        if record_all:
            self.set_status(
                "recording {} cameras -> payloads/{}/".format(len(streams), stamp)
            )
        else:
            self.set_status(
                "recording " + streams[0].camera.name + " -> " + self.recorders[0].output_dir.name + "/"
            )

    def set_status(self, message: str) -> None:
        """Show a short message along the bottom of the window."""
        self.status_bar.configure(text=message)

    def on_snapshot(self, event: tk.Event | None = None) -> None:
        """Save a picture from every working camera into the snapshots folder.

        The event argument is supplied by Tk when a key is pressed. It defaults
        to None so the method can also be called directly from code.
        """
        folder = self.config_data.snapshot_dir
        folder.mkdir(exist_ok=True)

        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        saved = 0
        for view in self.views:
            if view.save_image(folder, stamp) is not None:
                saved = saved + 1

        if saved > 0:
            self.set_status("saved {} picture(s) to {}/  ({})".format(saved, folder.name, stamp))
        else:
            self.set_status("nothing to save - no camera is sending pictures")

    def on_fullscreen(self, event: tk.Event | None = None) -> None:
        """Switch fullscreen on or off."""
        self.is_fullscreen = not self.is_fullscreen
        self.attributes("-fullscreen", self.is_fullscreen)

    def on_quit(self, event: tk.Event | None = None) -> None:
        """Stop any recording and every background reader, then close the window."""
        for recorder in self.recorders:
            recorder.stop()
        for stream in self.streams:
            stream.stop()
        self.destroy()


def parse_arguments() -> argparse.Namespace:
    """Read the command-line options."""
    parser = argparse.ArgumentParser(
        description="Live viewer for one IP camera and two webcams."
    )
    parser.add_argument(
        "--only",
        choices=["ipcam", "webcam"],
        help="show only cameras of this kind",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="print the configured cameras and exit",
    )
    return parser.parse_args()


def print_cameras(cameras: list[Camera]) -> None:
    """Print each configured camera, with its password hidden."""
    for camera in cameras:
        print("{:8} {:34} {}".format(camera.kind, camera.name, camera.safe_address()))


def main() -> int:
    """Start the app. Returns 0 when all went well, 1 on a setup problem."""
    arguments = parse_arguments()

    config = Config()
    cameras = config.cameras()

    if arguments.only:
        wanted = []
        for camera in cameras:
            if camera.kind == arguments.only:
                wanted.append(camera)
        cameras = wanted

    if arguments.list:
        print_cameras(cameras)
        return 0

    if not cameras:
        print("No cameras configured. Copy .env.example to .env and fill it in.", file=sys.stderr)
        return 1

    App(config, cameras).mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
