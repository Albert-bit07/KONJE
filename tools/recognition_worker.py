#!/usr/bin/env python3
"""Opt-in LOCAL experimentation adapter (non-clinical, no cloud or auto-download).

Reads up to three framed transient JPEGs from stdin; outputs one normalized embedding, or
UNCERTAIN if zero/multiple/low-quality faces. Does not store/log personal data.
Requires a separately provisioned, appropriately licensed InsightFace model pack.
The model pack path is NOT committed or downloaded by this project.
"""
import os
import sys
from pathlib import Path

MAX_JPEG = 4 * 1024 * 1024
MAX_FRAMES = 3


def uncertain() -> None:
    print("UNCERTAIN")


def main() -> int:
    root = os.environ.get("KONJE_MODEL_ROOT", "")
    pack = os.environ.get("KONJE_MODEL_PACK", "")
    if not root or not pack or not pack.replace("_", "").isalnum():
        uncertain()
        return 0
    if not (Path(root) / "models" / pack).is_dir():
        uncertain()
        return 0
    try:
        from worker_protocol import read_burst
        frames = read_burst(sys.stdin.buffer.read(7 + MAX_FRAMES * (4 + MAX_JPEG) + 1))
    except ValueError:
        uncertain()
        return 0
    try:
        import cv2
        import numpy as np
        from insightface.app import FaceAnalysis

        scored = []
        for data in frames:
            image = cv2.imdecode(np.frombuffer(data, dtype=np.uint8), cv2.IMREAD_COLOR)
            if image is None or image.shape[0] < 64 or image.shape[1] < 64:
                continue
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            sharpness = float(cv2.Laplacian(gray, cv2.CV_64F).var())
            # Development heuristic, NOT a validated image-quality or clinical threshold.
            if sharpness >= 20:
                scored.append((sharpness, image))
        if not scored:
            uncertain()
            return 0
        image = max(scored, key=lambda candidate: candidate[0])[1]
        app = FaceAnalysis(name=pack, root=root, providers=["CPUExecutionProvider"])
        app.prepare(ctx_id=-1, det_size=(640, 640))
        faces = app.get(image)
        if len(faces) != 1:
            uncertain()
            return 0
        face = faces[0]
        x1, y1, x2, y2 = face.bbox
        if float(x2 - x1) < 70 or float(y2 - y1) < 70 or float(face.det_score) < 0.8:
            uncertain()
            return 0
        embed = np.asarray(face.embedding, dtype=np.float32)
        norm = np.linalg.norm(embed)
        if not np.isfinite(embed).all() or not np.isfinite(norm) or norm < 1e-9:
            uncertain()
            return 0
        values = embed / norm
        print("EMBEDDING " + " ".join(format(float(v), ".9g") for v in values))
    except Exception:
        # Never emit personal information or model tracebacks over stdout.
        uncertain()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())