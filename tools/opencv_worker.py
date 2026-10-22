#!/usr/bin/env python3
"""Local, single-shot YuNet/SFace embedding worker for KONJE1 JPEG bursts.

No network requests, model downloads, image persistence, or biometric logging.
Only outputs EMBEDDING <float...> or UNCERTAIN to stdout.
"""
import os
import sys
from pathlib import Path

MAX_INPUT = 7 + 3 * (4 + 4 * 1024 * 1024)


def model_paths(env=None):
    """Require pinned model hashes and an embedding-space identifier."""
    from model_identity import verified_paths
    return verified_paths(env)


def extract(frames, detector_path, recognizer_path):
    """Return normalized embedding or None; every failure is a non-identification."""
    import cv2
    import numpy as np

    if not hasattr(cv2, "FaceDetectorYN") or not hasattr(cv2, "FaceRecognizerSF"):
        return None
    detector = cv2.FaceDetectorYN.create(str(detector_path), "", (320, 320), 0.9, 0.3, 5000)
    recognizer = cv2.FaceRecognizerSF.create(str(recognizer_path), "")
    candidates = []
    for raw in frames:
        image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None or min(image.shape[:2]) < 64:
            continue
        height, width = image.shape[:2]
        detector.setInputSize((width, height))
        _, faces = detector.detect(image)
        if faces is not None and len(faces) > 1:
            # A burst with multiple people is ambiguous; do not select another frame.
            return None
        if faces is None or len(faces) != 1:
            continue
        face = faces[0]
        if min(float(face[2]), float(face[3])) < 70 or float(face[-1]) < 0.9:
            continue
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if not np.isfinite(sharpness) or sharpness < 20:
            continue
        candidates.append((sharpness, image, face))
    if not candidates:
        return None
    _, image, face = max(candidates, key=lambda item: item[0])
    aligned = recognizer.alignCrop(image, face)
    embedding = np.asarray(recognizer.feature(aligned), dtype=np.float32).reshape(-1)
    if not 64 <= embedding.size <= 2048 or not np.isfinite(embedding).all():
        return None
    magnitude = float(np.linalg.norm(embedding))
    if not np.isfinite(magnitude) or magnitude < 1e-9:
        return None
    return embedding / magnitude


def run(source=sys.stdin.buffer, dest=sys.stdout):
    from worker_protocol import read_burst

    result = None
    try:
        paths = model_paths()
        if paths is not None:
            raw = source.read(MAX_INPUT + 1)
            if len(raw) <= MAX_INPUT:
                result = extract(read_burst(raw), *paths)
    except Exception:
        # Do not put frame contents, identity information, or traceback on stdout.
        result = None
    if result is None:
        dest.write("UNCERTAIN\n")
    else:
        dest.write("EMBEDDING " + " ".join(format(float(v), ".9g") for v in result) + "\n")
    dest.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())