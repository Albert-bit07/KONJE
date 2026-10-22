#!/usr/bin/env python3
"""Run actual local ONNX model initialization and synthetic-tensor inference.

This deliberately uses no photos, identities, profiles or volunteers. It checks
whether OpenCV can load and execute the two chosen model files on this machine.
It is NOT an accuracy, calibration or Raspberry Pi performance benchmark.
"""
import json
import sys

from model_identity import verified_paths


def smoke(paths, cv2, np):
    detector_path, recognition_path = paths
    if not hasattr(cv2, "FaceDetectorYN") or not hasattr(cv2, "FaceRecognizerSF"):
        raise RuntimeError("OpenCV face APIs unavailable")
    try:
        detector = cv2.FaceDetectorYN.create(str(detector_path), "", (320, 320))
    except Exception as error:
        raise RuntimeError("detector_load_" + type(error).__name__) from None
    try:
        recognizer = cv2.FaceRecognizerSF.create(str(recognition_path), "")
    except Exception as error:
        raise RuntimeError("recognizer_load_" + type(error).__name__) from None
    # Synthetic empty tensors avoid volunteer faces. Detector and embedder both execute.
    blank_frame = np.zeros((320, 320, 3), dtype=np.uint8)
    detector.setInputSize((320, 320))
    try:
        _, detected = detector.detect(blank_frame)
    except Exception as error:
        raise RuntimeError("detector_forward_" + type(error).__name__) from None
    # Detection output is not interpreted as a face; just check the execution succeeds.
    blank_aligned = np.zeros((112, 112, 3), dtype=np.uint8)
    try:
        embedding = np.asarray(recognizer.feature(blank_aligned), dtype=np.float32).reshape(-1)
    except Exception as error:
        raise RuntimeError("recognizer_forward_" + type(error).__name__) from None
    if not 64 <= embedding.size <= 2048 or not np.isfinite(embedding).all():
        raise RuntimeError("Embedding output has invalid shape or values")
    return {
        "result": "loaded_and_executed",
        "runtime": str(cv2.__version__),
        "embedding_dimensions": int(embedding.size),
        "detector_executed": True,
        "detector_rows_on_blank": 0 if detected is None else int(len(detected)),
        "image_source": "synthetic_blank_array",
        "recognition_accuracy_evaluated": False,
    }


def main():
    paths = verified_paths()
    if paths is None:
        print('{"result": "unavailable", "reason": "unpinned_or_missing_models"}')
        return 2
    try:
        import cv2
        import numpy as np
        result = smoke(paths, cv2, np)
    except (ImportError, ValueError, RuntimeError) as error:
        reason = str(error) if isinstance(error, RuntimeError) and str(error).startswith(("detector_", "recognizer_")) else type(error).__name__
        print(json.dumps({"result": "unavailable", "reason": reason}))
        return 2
    except Exception:
        # Do not log local model paths, image buffers or stack traces.
        print('{"result": "unavailable", "reason": "model_runtime_failure"}')
        return 2
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())