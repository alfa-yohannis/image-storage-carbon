"""Finds faces in a picture, and optionally works out whose face it is.

Two separate jobs, easy to confuse:

    Detection   - "there is a face, and it is here." Draws the green box.
    Recognition - "this face belongs to Alfa." Needs example photos first.

Detection always works. Recognition only names people you have enrolled by
putting photos in the known_faces/ folder; anyone else is shown as "unknown".

Both use models from the OpenCV Zoo, stored in models/:

    YuNet  - detection. Small (228 KB) and fast.
    SFace  - recognition. Turns a face into 128 numbers, its "embedding".
             Two pictures of the same person give similar numbers, so comparing
             them tells you whether it is the same person.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
MODEL_DIR = HERE / "models"
KNOWN_FACES_DIR = HERE / "known_faces"

DETECTOR_MODEL = MODEL_DIR / "face_detection_yunet_2023mar.onnx"
RECOGNIZER_MODEL = MODEL_DIR / "face_recognition_sface_2021dec.onnx"

# Faces smaller than this many pixels across are usually too blurred to be
# useful, and reporting them only makes the picture look busy.
MIN_FACE_WIDTH = 40

# Detection runs on a shrunken copy. A large picture takes far longer to search
# and finds the same faces, so we search a small one and scale the answer back.
DETECT_WIDTH = 480

# How sure the detector must be before it reports a face, from 0 to 1.
#
# YuNet's own default is 0.9, which is too strict for real cameras: a laptop
# webcam produces a softer, noisier picture than a photograph, and a face that
# is plainly visible to a person scores only about 0.5. At 0.9 those faces are
# silently discarded and the camera looks broken. 0.5 finds them while still
# rejecting most background clutter. Lower it further only if faces are missed,
# since the false alarms grow quickly below about 0.4.
DEFAULT_MIN_CONFIDENCE = 0.5

# How alike two faces must be before we call them the same person. SFace uses
# cosine similarity, from -1 to 1. The value recommended for this model is 0.363;
# raising it makes the app stricter and more likely to answer "unknown".
MATCH_THRESHOLD = 0.363


@dataclass(frozen=True)
class Face:
    """One face found in a picture.

    Fields:
        x, y:       top-left corner of the box, in the full picture's pixels.
        width:      how wide the box is.
        height:     how tall the box is.
        confidence: how sure the detector is, from 0 to 1.
        name:       who it is, or "" when recognition is switched off, or
                    "unknown" when nobody enrolled matches.
    """

    x: int
    y: int
    width: int
    height: int
    confidence: float
    name: str = ""

    def label(self) -> str:
        """Return the text to draw above the box."""
        if not self.name:
            return "{:.0%}".format(self.confidence)
        return "{} {:.0%}".format(self.name, self.confidence)


class FaceDetector:
    """Finds where the faces are, using the YuNet model."""

    def __init__(
        self,
        model_path: Path = DETECTOR_MODEL,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ) -> None:
        """Load the detector. Raises FileNotFoundError when the model is missing."""
        if not model_path.exists():
            raise FileNotFoundError(
                "Face detection model not found at " + str(model_path) + ".\n"
                "Download it with:\n"
                "  curl -sSL -o " + str(model_path) + " \\\n"
                "    https://github.com/opencv/opencv_zoo/raw/main/models/"
                "face_detection_yunet/face_detection_yunet_2023mar.onnx"
            )

        # The size given here is replaced before every search, because each
        # camera sends a different picture size. The fourth value is the
        # confidence threshold - leaving it at OpenCV's default of 0.9 is the
        # usual reason a working camera appears to find no faces.
        self._detector = cv2.FaceDetectorYN.create(
            str(model_path), "", (320, 320), min_confidence
        )

    def detect(self, image: np.ndarray) -> list[Face]:
        """Return every face found in the picture, with boxes in its own pixels."""
        if image is None or image.size == 0:
            return []

        small, scale = self._shrink(image)
        height, width = small.shape[:2]

        self._detector.setInputSize((width, height))
        _, raw = self._detector.detect(small)
        if raw is None:
            return []

        faces = []
        for row in raw:
            # Each row is: x, y, w, h, then five facial landmarks, then a score.
            x, y, box_width, box_height = row[0:4]
            confidence = float(row[-1])

            # Undo the shrink so the box lines up with the original picture.
            x = int(x / scale)
            y = int(y / scale)
            box_width = int(box_width / scale)
            box_height = int(box_height / scale)

            if box_width < MIN_FACE_WIDTH:
                continue

            faces.append(Face(x, y, box_width, box_height, confidence))

        return faces

    def _shrink(self, image: np.ndarray) -> tuple[np.ndarray, float]:
        """Return a smaller copy for searching, and the factor it was shrunk by.

        Searching a 1920-wide picture is several times slower than searching a
        480-wide one and finds the same faces, so this is nearly free accuracy.
        """
        height, width = image.shape[:2]
        if width <= DETECT_WIDTH:
            return image, 1.0

        scale = DETECT_WIDTH / width
        new_size = (DETECT_WIDTH, max(1, int(height * scale)))
        return cv2.resize(image, new_size, interpolation=cv2.INTER_AREA), scale


class FaceRecognizer:
    """Works out whose face it is, by comparing against enrolled photos.

    Enrol someone by saving a clear photo of their face as
    known_faces/their_name.jpg. The file name becomes the label shown on screen.
    """

    def __init__(
        self,
        model_path: Path = RECOGNIZER_MODEL,
        known_dir: Path = KNOWN_FACES_DIR,
    ) -> None:
        """Load the model and learn every face in the known_faces folder."""
        if not model_path.exists():
            raise FileNotFoundError("Face recognition model not found at " + str(model_path))

        self._recognizer = cv2.FaceRecognizerSF.create(str(model_path), "")
        self._names: list[str] = []
        self._embeddings: list[np.ndarray] = []
        self._load_known_faces(known_dir)

    def has_known_faces(self) -> bool:
        """True when at least one person has been enrolled."""
        return len(self._names) > 0

    def known_names(self) -> list[str]:
        """The names of everyone enrolled."""
        return list(self._names)

    def identify(self, image: np.ndarray, face: Face) -> str:
        """Return the name of the person in the box, or "unknown"."""
        if not self._names:
            return ""

        embedding = self._embed(image, face)
        if embedding is None:
            return "unknown"

        best_name = "unknown"
        best_score = MATCH_THRESHOLD
        for name, known in zip(self._names, self._embeddings):
            score = self._recognizer.match(embedding, known, cv2.FaceRecognizerSF_FR_COSINE)
            if score > best_score:
                best_score = score
                best_name = name

        return best_name

    def _embed(self, image: np.ndarray, face: Face) -> np.ndarray | None:
        """Turn one face into the numbers that describe it, or None on failure."""
        # SFace expects the box in the same 15-value layout the detector produces.
        # Only the first four values are used for alignment here.
        box = np.array(
            [[face.x, face.y, face.width, face.height] + [0.0] * 11],
            dtype=np.float32,
        )
        try:
            aligned = self._recognizer.alignCrop(image, box)
            return self._recognizer.feature(aligned)
        except cv2.error:
            # A face touching the edge of the picture cannot be aligned.
            return None

    def _load_known_faces(self, known_dir: Path) -> None:
        """Read every photo in the folder and remember what each person looks like."""
        if not known_dir.is_dir():
            return

        detector = FaceDetector()
        for path in sorted(known_dir.iterdir()):
            if path.suffix.lower() not in (".jpg", ".jpeg", ".png"):
                continue

            image = cv2.imread(str(path))
            if image is None:
                continue

            found = detector.detect(image)
            if not found:
                print("[faces] no face found in " + path.name + " - skipped")
                continue

            # Use the largest face, in case the photo has more than one person.
            largest = max(found, key=lambda f: f.width * f.height)
            embedding = self._embed(image, largest)
            if embedding is None:
                continue

            self._names.append(path.stem)
            self._embeddings.append(embedding)
            print("[faces] enrolled " + path.stem)


class FaceFinder:
    """Detection and recognition together, as one thing the camera can use.

    Recognition is optional: when it is switched off, or no one is enrolled, the
    boxes still appear but carry no name.
    """

    def __init__(
        self,
        recognise: bool = False,
        min_confidence: float = DEFAULT_MIN_CONFIDENCE,
    ) -> None:
        """Load the detector, and the recogniser too when asked for."""
        self.detector = FaceDetector(min_confidence=min_confidence)
        self.recognizer: FaceRecognizer | None = None

        if recognise:
            try:
                recognizer = FaceRecognizer()
            except FileNotFoundError as error:
                print("[faces] recognition off: " + str(error))
                return

            if recognizer.has_known_faces():
                self.recognizer = recognizer
            else:
                print(
                    "[faces] recognition on but nobody is enrolled - add photos to "
                    + KNOWN_FACES_DIR.name
                    + "/"
                )

    def find(self, image: np.ndarray) -> list[Face]:
        """Return the faces in the picture, named when recognition is available."""
        found = self.detector.detect(image)
        if self.recognizer is None:
            return found

        named = []
        for face in found:
            name = self.recognizer.identify(image, face)
            named.append(
                Face(face.x, face.y, face.width, face.height, face.confidence, name)
            )
        return named
