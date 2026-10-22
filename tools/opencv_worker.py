#!/usr/bin/env python3
"""Local YuNet/SFace embedding worker; never stores or logs image bytes.

The single-shot interface consumes KONJE1 bursts from stdin. The persistent
server uses load_models() and extract_loaded() with the same selection rules.
"""
import os
import sys

MAX_INPUT = 7 + 3 * (4 + 4 * 1024 * 1024)


def model_paths(env=None):
    from model_identity import verified_paths
    return verified_paths(env)


def load_models(detector_path, recognizer_path):
    import cv2
    import numpy as np
    if not hasattr(cv2, "FaceDetectorYN") or not hasattr(cv2, "FaceRecognizerSF"):
        raise RuntimeError("OpenCV face APIs unavailable")
    detector = cv2.FaceDetectorYN.create(str(detector_path), "", (320, 320), 0.9, 0.3, 5000)
    recognizer = cv2.FaceRecognizerSF.create(str(recognizer_path), "")
    return (cv2, np, detector, recognizer)


def extract_loaded(frames, runtime):
    """Run a single bounded burst using preloaded models, or return uncertain."""
    cv2, np, detector, recognizer = runtime
    candidates = []
    for raw in frames:
        image = cv2.imdecode(np.frombuffer(raw, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None or min(image.shape[:2]) < 64:
            continue
        height, width = image.shape[:2]
        detector.setInputSize((width, height))
        _, faces = detector.detect(image)
        if faces is not None and len(faces) > 1:
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


def extract(frames, detector_path, recognizer_path):
    return extract_loaded(frames, load_models(detector_path, recognizer_path))


def format_result(embedding):
    if embedding is None:
        return b"UNCERTAIN\n"
    return ("EMBEDDING " + " ".join(format(float(v), ".9g") for v in embedding) + "\n").encode("ascii")


def run(source=None, dest=None):
    from worker_protocol import read_burst
    if source is None:
        source = sys.stdin.buffer
    if dest is None:
        dest = sys.stdout
    result = None
    try:
        paths = model_paths()
        if paths is not None:
            raw = source.read(MAX_INPUT + 1)
            if len(raw) <= MAX_INPUT:
                result = extract(read_burst(raw), *paths)
    except Exception:
        result = None
    dest.write(format_result(result).decode("ascii"))
    dest.flush()
    return 0


if __name__ == "__main__":
    raise SystemExit(run())