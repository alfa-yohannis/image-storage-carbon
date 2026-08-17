"""Media payload generation: a synthetic collage, or real recorded camera frames.

Two payload sources exist, chosen with BENCHMARK_PAYLOAD_SOURCE:

``collage``
    The original behaviour. One deterministic collage is built per resolution
    and inserted for every row, so all rows are byte-identical.

``frames``
    Real JPEG frames recorded from a camera (see ``code_realcase/record.py``), resized
    to the profile resolution. Every row receives a *different* picture.

The distinction matters for storage measurements. Identical rows let a database
compress the repetition in a way real data never permits: MongoDB packs many
rows into one bucket and Snappy removes the duplication almost entirely, which
depresses its storage amplification at low resolution. Real frames remove that
artefact.
"""
from __future__ import annotations

import subprocess
import tempfile
from dataclasses import dataclass, replace
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps

from config import WorkloadProfile


@dataclass(frozen=True)
class MediaPayload:
    profile_name: str
    payload_kind: str
    mime_type: str
    codec: str
    width: int
    height: int
    duration_ms: int
    payload_bytes: bytes

    @property
    def payload_size_bytes(self) -> int:
        return len(self.payload_bytes)

    @property
    def payload_size_mb(self) -> float:
        return len(self.payload_bytes) / (1024 * 1024)


class PayloadSource:
    """Supplies the payload for each inserted row.

    ``representative()`` is the payload used for reporting (profile name, size,
    dimensions); ``next()`` is called once per row during insertion.
    """

    def representative(self) -> MediaPayload:
        raise NotImplementedError

    def next(self) -> MediaPayload:
        raise NotImplementedError

    def describe(self) -> str:
        raise NotImplementedError


class SinglePayloadSource(PayloadSource):
    """Serves one payload for every row - the original, identical-rows behaviour."""

    def __init__(self, payload: MediaPayload):
        self._payload = payload

    def representative(self) -> MediaPayload:
        return self._payload

    def next(self) -> MediaPayload:
        return self._payload

    def describe(self) -> str:
        return f"collage, identical rows ({self._payload.payload_size_mb:.2f} MB)"


class FrameSequenceSource(PayloadSource):
    """Cycles through real recorded frames, one distinct picture per row.

    Frames are resized and re-encoded once up front, outside the measured
    region, so insertion measures storage and not image processing. The pool is
    capped at ``pool_size`` to bound memory; if fewer frames exist than rows,
    the sequence wraps and some frames repeat.
    """

    def __init__(self, payloads: list[MediaPayload], source_count: int):
        if not payloads:
            raise ValueError("FrameSequenceSource needs at least one frame")
        self._payloads = payloads
        self._source_count = source_count
        self._index = 0
        sizes = [p.payload_size_bytes for p in payloads]
        self._mean_size = sum(sizes) / len(sizes)

    def representative(self) -> MediaPayload:
        """Return the frame closest to the mean size, so reported figures are typical."""
        return min(self._payloads, key=lambda p: abs(p.payload_size_bytes - self._mean_size))

    def next(self) -> MediaPayload:
        payload = self._payloads[self._index]
        self._index = (self._index + 1) % len(self._payloads)
        return payload

    def describe(self) -> str:
        return (
            f"real frames, {len(self._payloads)} distinct of {self._source_count} available "
            f"(mean {self._mean_size / (1024 * 1024):.2f} MB)"
        )


class RoundRobinSource(PayloadSource):
    """Interleaves several cameras into one stream: cam 1, cam 2, cam 3, cam 1, ...

    This models a *centralised ingest service* - cameras feed one application,
    which writes to the database - rather than each camera opening its own
    connection. It is how most image pipelines are actually built, and unlike
    true concurrency it stays deterministic, so a difference against the
    published single-camera results is attributable to the workload rather than
    to thread scheduling.

    The cameras may differ in resolution, which is the point: a real installation
    stores a mixed fleet, not one resolution at a time.
    """

    def __init__(self, sources: list[PayloadSource], labels: list[str]):
        if not sources:
            raise ValueError("RoundRobinSource needs at least one camera")
        self._sources = sources
        self._labels = labels
        self._index = 0

    def representative(self) -> MediaPayload:
        """Return the median-sized camera's representative frame."""
        ordered = sorted(self._sources, key=lambda s: s.representative().payload_size_bytes)
        return ordered[len(ordered) // 2].representative()

    def next(self) -> MediaPayload:
        payload = self._sources[self._index].next()
        self._index = (self._index + 1) % len(self._sources)
        return payload

    def describe(self) -> str:
        parts = []
        for label, source in zip(self._labels, self._sources):
            payload = source.representative()
            parts.append(f"{label} {payload.width}x{payload.height}")
        return f"round-robin over {len(self._sources)} cameras: " + ", ".join(parts)


class PayloadFactory:
    """Builds deterministic payloads for a given source asset."""

    def __init__(self, source_image_path: Path):
        self.source_image_path = Path(source_image_path)

    def build(self, profile: WorkloadProfile) -> MediaPayload:
        if not self.source_image_path.exists():
            raise FileNotFoundError(f"Source asset not found: {self.source_image_path}")
        if profile.payload_kind == "image":
            return self._build_image(profile)
        return self._build_video(profile)

    def _build_collage(self, width: int, height: int) -> Image.Image:
        src = Image.open(self.source_image_path).convert("RGB")
        tile_w = max(width // 2, 1)
        tile_h = max(height // 2, 1)
        fit = lambda im: ImageOps.fit(im, (tile_w, tile_h), method=Image.Resampling.LANCZOS)
        variants = [
            fit(src),
            ImageOps.mirror(fit(src)),
            ImageOps.flip(fit(src)),
            ImageOps.mirror(ImageOps.flip(fit(src))),
        ]
        canvas = Image.new("RGB", (width, height))
        for image, position in zip(variants, [(0, 0), (tile_w, 0), (0, tile_h), (tile_w, tile_h)], strict=True):
            canvas.paste(image, position)
        return canvas.crop((0, 0, width, height))

    def _build_image(self, profile: WorkloadProfile) -> MediaPayload:
        image = self._build_collage(profile.width, profile.height)
        buf = BytesIO()
        image.save(buf, format="JPEG", quality=profile.image_quality or 95, optimize=True)
        return MediaPayload(
            profile_name=profile.name, payload_kind=profile.payload_kind,
            mime_type=profile.mime_type, codec=profile.codec,
            width=profile.width, height=profile.height, duration_ms=0,
            payload_bytes=buf.getvalue(),
        )

    def build_frame_sequence(
        self, frames_dir: Path, profile: WorkloadProfile, pool_size: int
    ) -> FrameSequenceSource:
        """Encode real recorded frames at the profile's resolution.

        Frames larger than the profile are downscaled. Frames *smaller* than the
        profile are refused rather than upscaled: enlarging invents detail the
        camera never captured, which would change the JPEG entropy that drives
        the storage and carbon results.
        """
        paths = sorted(Path(frames_dir).glob("frame_*.jpg"))
        if not paths:
            raise FileNotFoundError(f"No frames found in {frames_dir}")

        with Image.open(paths[0]) as probe:
            source_w, source_h = probe.size
        if profile.width > source_w or profile.height > source_h:
            raise ValueError(
                f"{profile.name} ({profile.width}x{profile.height}) exceeds the recorded "
                f"frame size ({source_w}x{source_h}); real frames cannot be upscaled"
            )

        payloads: list[MediaPayload] = []
        for path in paths[:pool_size]:
            with Image.open(path) as raw:
                image = ImageOps.fit(
                    raw.convert("RGB"),
                    (profile.width, profile.height),
                    method=Image.Resampling.LANCZOS,
                )
            buf = BytesIO()
            image.save(buf, format="JPEG", quality=profile.image_quality or 95, optimize=True)
            payloads.append(
                MediaPayload(
                    profile_name=profile.name, payload_kind=profile.payload_kind,
                    mime_type=profile.mime_type, codec=profile.codec,
                    width=profile.width, height=profile.height, duration_ms=0,
                    payload_bytes=buf.getvalue(),
                )
            )
        return FrameSequenceSource(payloads, len(paths))

    def build_fleet_sequence(
        self, fleet_dir: Path, profile: WorkloadProfile, pool_size: int
    ) -> RoundRobinSource:
        """Round-robin over every camera in fleet_dir, each at its own resolution.

        Each subfolder is one camera, as written by code_realcase/record.py:

            fleet_dir/Tapo_IP_Cam.../frame_00000.jpg      1920x1080
            fleet_dir/Webcam_2.../frame_00000.jpg         1280x720
            fleet_dir/Webcam_1.../frame_00000.jpg          640x480

        Cameras keep their **native** resolution rather than being forced to a
        common one. That is the point of the fleet workload: a real installation
        mixes camera types, so the database receives 1080p, 720p and 480p frames
        interleaved, not one resolution at a time. Forcing a shared resolution
        would either discard the smaller cameras or upscale them, and upscaling
        invents detail that changes the JPEG entropy the results depend on.

        ``profile`` only supplies the encoding quality and labels the run; it
        does not dictate the resolution of any camera.
        """
        fleet_dir = Path(fleet_dir)
        cameras = sorted(p for p in fleet_dir.iterdir() if p.is_dir()) if fleet_dir.is_dir() else []
        if not cameras:
            raise FileNotFoundError(f"No camera folders found in {fleet_dir}")

        sources: list[PayloadSource] = []
        labels: list[str] = []
        # Split the pool evenly so every camera contributes the same row count.
        per_camera = max(1, pool_size // len(cameras))

        for camera_dir in cameras:
            try:
                native = self._native_profile(camera_dir, profile)
                sources.append(self.build_frame_sequence(camera_dir, native, per_camera))
                labels.append(camera_dir.name.split("_")[0])
            except (FileNotFoundError, ValueError) as exc:
                print(f"   ! skipping camera {camera_dir.name}: {exc}")

        if not sources:
            raise ValueError(f"No camera in {fleet_dir} supplied usable frames")
        return RoundRobinSource(sources, labels)

    def _native_profile(self, camera_dir: Path, template: WorkloadProfile) -> WorkloadProfile:
        """Return a profile matching this camera's own recorded frame size.

        The encoding settings are taken from ``template`` so every camera is
        compressed identically; only the dimensions come from the camera.
        """
        frames = sorted(Path(camera_dir).glob("frame_*.jpg"))
        if not frames:
            raise FileNotFoundError(f"No frames in {camera_dir}")
        with Image.open(frames[0]) as probe:
            width, height = probe.size
        return replace(template, name=f"{template.name}_{width}x{height}",
                       width=width, height=height)

    def _build_video(self, profile: WorkloadProfile) -> MediaPayload:
        collage = self._build_collage(profile.width, profile.height)
        duration_sec = profile.video_duration_sec or 3.0
        fps = profile.video_fps or 24
        crf = profile.video_crf or 23
        with tempfile.TemporaryDirectory(prefix="media_payload_") as tmpdir:
            tmp = Path(tmpdir)
            frame_path, output_path = tmp / "source.jpg", tmp / "payload.mp4"
            collage.save(frame_path, format="JPEG", quality=96, optimize=True)
            cmd = [
                "ffmpeg", "-y", "-loop", "1", "-framerate", str(fps),
                "-t", f"{duration_sec:.2f}", "-i", str(frame_path),
                "-vf", f"scale={profile.width}:{profile.height},noise=alls=18:allf=t+u:all_seed=23",
                "-c:v", "libx264", "-preset", "medium", "-crf", str(crf),
                "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output_path),
            ]
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            payload_bytes = output_path.read_bytes()
        return MediaPayload(
            profile_name=profile.name, payload_kind=profile.payload_kind,
            mime_type=profile.mime_type, codec=profile.codec,
            width=profile.width, height=profile.height,
            duration_ms=int(duration_sec * 1000), payload_bytes=payload_bytes,
        )
