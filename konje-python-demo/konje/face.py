"""Face finding and face matching.

Uses the same two OpenCV models Albert's KONJE repo picked:
  - YuNet  : finds where faces are in a picture (a box around each face)
  - SFace  : turns a face into 128 numbers (an "embedding"). Two photos of the
             same person give similar numbers; different people give different ones.
"""
from pathlib import Path

import cv2
import numpy as np

MODELS = Path(__file__).resolve().parent.parent / "models"
DETECTOR_FILE = MODELS / "face_detection_yunet_2023mar.onnx"
RECOGNIZER_FILE = MODELS / "face_recognition_sface_2021dec.onnx"

# How sure we must be before saying a name. Cosine similarity runs from -1 to 1;
# OpenCV's own guidance for SFace is "same person" at about 0.36 and above.
# We are stricter, and also require the best match to beat the runner-up by a
# margin, so two similar-looking people never get mixed up.
MATCH_THRESHOLD = 0.45
MATCH_MARGIN = 0.06
MIN_FACE_PIXELS = 60  # ignore tiny faces far in the background


class FaceEngine:
    def __init__(self):
        if not DETECTOR_FILE.exists() or not RECOGNIZER_FILE.exists():
            raise SystemExit("Face models missing. Run:  python download_models.py")
        self.detector = cv2.FaceDetectorYN.create(str(DETECTOR_FILE), "", (320, 320), 0.85, 0.3, 20)
        self.recognizer = cv2.FaceRecognizerSF.create(str(RECOGNIZER_FILE), "")

    def find_faces(self, frame):
        """Return a list of faces, biggest (closest to the camera) first.
        Each face is 15 numbers: x, y, width, height, 5 landmark points, score."""
        h, w = frame.shape[:2]
        self.detector.setInputSize((w, h))
        _, faces = self.detector.detect(frame)
        if faces is None:
            return []
        faces = [f for f in faces if min(f[2], f[3]) >= MIN_FACE_PIXELS]
        return sorted(faces, key=lambda f: f[2] * f[3], reverse=True)

    def embed(self, frame, face):
        """Turn one face into a unit-length list of 128 numbers."""
        aligned = self.recognizer.alignCrop(frame, face)
        vec = np.asarray(self.recognizer.feature(aligned), dtype=np.float32).reshape(-1)
        return vec / (np.linalg.norm(vec) + 1e-9)


def similarity(a, b):
    """Cosine similarity of two unit vectors: 1.0 = identical, 0 = unrelated."""
    return float(np.dot(a, b))


def best_match(embedding, people):
    """Compare a face against every enrolled person.

    Returns (person or None, best_score, runner_up_score). None means
    "not sure", and the glasses then say "Person not recognized" instead of guessing.
    """
    scored = []
    for person in people:
        scores = [similarity(embedding, np.asarray(e, dtype=np.float32)) for e in person["embeddings"]]
        scored.append((max(scores), person))
    if not scored:
        return None, 0.0, 0.0
    scored.sort(key=lambda s: s[0], reverse=True)
    best_score, best_person = scored[0]
    runner_up = scored[1][0] if len(scored) > 1 else 0.0
    if best_score >= MATCH_THRESHOLD and best_score - runner_up >= MATCH_MARGIN:
        return best_person, best_score, runner_up
    return None, best_score, runner_up
