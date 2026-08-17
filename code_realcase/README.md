# Camera Wall — live viewer for one IP camera and two webcams

A small Tkinter desktop app that shows three cameras side by side: a **Tapo IP camera** over the
network and **two USB webcams**. Each camera is read in its own background thread, so one camera being
unplugged or offline never freezes the window — it simply shows as *disconnected* and keeps retrying.

```
┌──────────────────────┬──────────────────────┐
│  Tapo IP Cam         │  Webcam 1            │
│  live   30.5 fps     │  live   23.3 fps     │
│  1920x1080           │  1280x720            │
├──────────────────────┼──────────────────────┤
│  Webcam 2            │  Cameras             │
│  live   12.4 fps     │  - rtsp://user:****@ │
│  1280x720            │  - 0                 │
│                      │  - 4                 │
└──────────────────────┴──────────────────────┘
  s = snapshot     f = fullscreen     q / Esc = quit
```

The window opens centred on the screen. See [Cameras on this machine](#cameras-on-this-machine)
for the measured capability of each device.

## Requirements

- **Python 3.10 or newer** (uses the `str | None` type syntax).
- **Tkinter**, which is not installable with pip. On Debian/Ubuntu:
  ```bash
  sudo apt install python3-tk
  ```
- A Tapo (or any RTSP) camera on the same network, and one or two USB webcams.

Everything else — OpenCV, Pillow, python-dotenv — installs itself on first run.

## Setup

Copy the example settings and fill in your own camera details:

```bash
cp .env.example .env
```

For the Tapo camera, `TAPO_USERNAME` and `TAPO_PASSWORD` are the **Camera Account** you create in the
Tapo mobile app under *Settings → Advanced Settings → Camera Account*. They are **not** your TP-Link
cloud login — using the cloud login is the most common reason the IP camera will not connect.

Find your webcam numbers with:

```bash
ls /dev/video*                # 0, 2 are usually the two capture devices
v4l2-ctl --list-devices       # clearer, if v4l-utils is installed
```

## Running

```bash
python3 app.py
```

The first run creates a `.venv` folder, installs the packages, and restarts itself inside it. That
takes a couple of minutes; later runs start immediately.

```bash
python3 app.py --list          # print the cameras it found, then exit
python3 app.py --only webcam    # webcams only, skip the IP camera
python3 app.py --only ipcam     # IP camera only
```

| Key | Action |
|---|---|
| `s` | Save a picture from every working camera into `snapshots/` |
| `f` | Toggle fullscreen |
| `q` or `Esc` | Quit |

## Cameras on this machine

Measured on the development laptop, 2026-08-14. Your own hardware will differ — re-run
`python3 app.py --list` and the checks below to confirm.

### 1. Tapo IP camera — `192.168.1.100`

| | |
|---|---|
| Connection | RTSP over TCP, port 554 |
| `stream1` | **1920×1080**, declared 25 fps, measured ~30 fps |
| `stream2` | **1280×720**, declared 25 fps, measured ~27 fps |
| Colour | Yes |

Set `TAPO_STREAM=stream2` if the network struggles or the video lags — it halves the data
without changing anything else.

### 2. Webcam 1 — `/dev/video0`, laptop built-in

| | |
|---|---|
| Reported name | `Integrated Camera: Integrated C` |
| Maximum | **1280×720 @ 30 fps** (MJPG) |
| Also supports | 640×480, 640×360, all @ 30 fps |
| Requesting 1920×1080 | Silently falls back to 1280×720 |
| Colour | Yes |

### 3. Webcam 2 — `/dev/video4`, external USB

| | |
|---|---|
| Reported name | `1080P Pro HD Webcam` |
| Maximum | **1920×1080 @ 30 fps** (MJPG) |
| Also supports | 1280×720, 640×480, all @ 30 fps |
| Minimum | 640×480 — a 640×360 request returns 640×480 |
| Colour | Yes |

This is the only camera here that genuinely does 1080p. The app currently runs it at 720p
because `WEBCAM_WIDTH`/`WEBCAM_HEIGHT` apply to both webcams at once; raise them if you want
full resolution and can accept webcam 1 capping at 720p.

### Not used — `/dev/video2`, laptop infrared sensor

| | |
|---|---|
| Reported name | `Integrated Camera: Integrated I` |
| Fixed at | **640×360 @ 30 fps**, greyscale — every larger request falls back to this |
| Colour | No — infrared |

This is the face-unlock sensor. It is skipped by default because it is low-resolution and
greyscale, but for **face recognition it is genuinely useful**: infrared defeats someone holding
up a printed photo, and it works in complete darkness. Set `WEBCAM_2_INDEX=2` to use it.

> Each camera claims two `/dev/video` numbers — `0`/`1`, `2`/`3`, `4`/`5`. Only the first of each
> pair delivers pictures; the second carries metadata.

### Frame rate is set by the format, not by our code

The same camera at the same resolution runs three times faster in one pixel format than the other:

| Device | Format | Driver declares | Measured |
|---|---|---|---|
| video0 | YUYV | 10 fps | 9.9 |
| video0 | **MJPG** | 30 fps | **30.2** |
| video4 | YUYV | 10 fps | 10.0 |
| video4 | **MJPG** | 30 fps | **24.9** |

Raw YUYV at 1280×720 is 1.84 MB per picture, so 30 per second would need 55 MB/s — more than
USB 2.0 carries in practice. The camera therefore only offers 10 fps in that format. MJPG makes
the camera compress each picture to roughly 50–100 KB first, and 30 fps fits comfortably. The app
requests MJPG for exactly this reason.

Measured matches declared within 2%, which shows the app itself is not the bottleneck.

**Running both webcams at once halves the second one** — webcam 2 drops from ~25 to ~12 fps
because the two share USB bandwidth. Lower the resolution, or move one camera to a port on a
different controller.

### What can be controlled from code

Settings are **requests, not commands**. The driver picks the nearest mode it supports and falls
back silently, so always read a value back to learn what you actually got — asking video0 for
1920×1080 returns 1280×720, and asking video4 for 640×360 returns 640×480, neither with any error.

| Property | video0 | video4 | What it does |
|---|---|---|---|
| `CAP_PROP_FOURCC` | yes | yes | **Pixel format — the one big lever, 3× the frame rate** |
| `CAP_PROP_FRAME_WIDTH` / `HEIGHT` | yes | yes | Resolution; snaps to a supported size |
| `CAP_PROP_FPS` | **ignored** | **ignored** | Asked for 15, stayed at 30 |
| `CAP_PROP_BRIGHTNESS` / `CONTRAST` / `SATURATION` | yes | yes | Picture quality |
| `CAP_PROP_EXPOSURE` / `AUTO_EXPOSURE` | yes | yes | Low-light behaviour |
| `CAP_PROP_AUTOFOCUS` | no | **yes** | Only the external camera focuses |
| `CAP_PROP_GAIN` / `ZOOM` | no | no | Returns −1, unsupported |

**Frame rate cannot be set directly** on either camera. It is a *consequence* of the format and
resolution, and of how much bandwidth the USB bus has left. To run slower than the camera offers,
you would have to discard frames in your own code.

Two rates exist and only one is ours:

- **Capture rate** — set by the hardware. `capture.read()` blocks until the camera delivers, so the
  camera paces the loop and the app simply keeps up.
- **Display rate** — `TARGET_FPS` in `.env`, how often the window redraws. It samples the newest
  picture; at 30 fps capture and 25 fps display, five pictures a second are never drawn. This
  changes what you *see*, never what the camera *makes*.

## How it works

Three modules, each with one job:

| File | Responsibility |
|---|---|
| `config.py` | Reads `.env` and produces `Camera` objects. The only module that touches environment variables. |
| `capture.py` | One `Stream` per camera. Each runs a background thread that reads pictures non-stop and keeps the newest. |
| `app.py` | Builds the window. Every 40 ms it asks each `Stream` for its newest picture and draws it. |

**Why background threads?** Asking a camera for a picture takes a moment. If the window waited for
that, it would freeze between pictures and stop responding to keys. Reading non-stop also matters for
network cameras: if pictures are read only occasionally, unread ones pile up inside the connection and
the video drifts seconds behind real time.

The threads and the window share data through a **lock** — a token only one thread may hold at a time —
so they never touch the same value simultaneously.

## Configuration reference

Set in `.env`:

| Setting | Meaning |
|---|---|
| `TAPO_USERNAME` / `TAPO_PASSWORD` | Camera Account credentials from the Tapo app |
| `IP_ADDRESS` | The camera's address on your network, e.g. `192.168.1.100` |
| `TAPO_STREAM` | `stream1` = HD, `stream2` = smaller and lighter on the CPU |
| `TAPO_RTSP_PORT` | Almost always `554` |
| `IPCAM_URL` | A complete `rtsp://` link — overrides all the Tapo settings above, for other brands |
| `WEBCAM_1_INDEX` / `WEBCAM_2_INDEX` | Device numbers; `0` means `/dev/video0` |
| `WEBCAM_WIDTH` / `WEBCAM_HEIGHT` | Requested webcam picture size |
| `TARGET_FPS` | How often the window redraws |

## Troubleshooting

**The IP camera stays "disconnected".**
Check the Camera Account credentials first — the cloud login will not work. Then confirm the camera is
reachable and the stream path is right:

```bash
ping 192.168.1.100
ffplay "rtsp://user:password@192.168.1.100:554/stream1"
```

**A webcam stays "disconnected" or shows the wrong camera.**
The index is wrong. Cameras usually claim two device numbers each (`0`/`1`, then `2`/`3`), and only the
first of each pair delivers pictures. Try `WEBCAM_2_INDEX=4` if you have three cameras attached.

**The picture is small — 640x360 when you asked for 1280x720.**
That camera does not support the size you requested and quietly fell back. Check what it can do:

```bash
v4l2-ctl --device=/dev/video2 --list-formats-ext
```

**Low frame rate.**
The app already requests MJPG, which lifts most webcams from about 10 fps to 25-30. If it is still
slow, the USB bus may be saturated — two cameras at 1080p on one controller is often too much. Lower
`WEBCAM_WIDTH`/`WEBCAM_HEIGHT`, or switch the IP camera to `TAPO_STREAM=stream2`.

**The video lags behind reality.** Use `stream2`, or check Wi-Fi signal strength at the camera.

## Security

`.env` holds your camera password in plain text. It is listed in `.gitignore` and **must never be
committed**. `snapshots/` is ignored too, since pictures of a real space may show people.

If the password has already been committed somewhere, change it in the Tapo app — removing the file
later does not remove it from a repository's history.
