#!/usr/bin/env python3
"""Local-only model readiness and latency probe. Never stores images or embeddings."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics
import sys
import time


def inspect_model(path):
    if not path:
        return {"ready": False, "reason": "not_configured"}
    p = Path(path)
    if not p.is_file() or p.suffix.lower() != '.onnx':
        return {"ready": False, "reason": "missing_or_wrong_extension"}
    if p.stat().st_size < 1024:
        return {"ready": False, "reason": "implausibly_small"}
    h = hashlib.sha256()
    with p.open('rb') as src:
        for chunk in iter(lambda: src.read(1024 * 1024), b''):
            h.update(chunk)
    return {"ready": True, "bytes": p.stat().st_size, "sha256": h.hexdigest()}


def percentile(samples, percent):
    ordered = sorted(samples)
    return ordered[max(0, min(len(ordered)-1, int((len(ordered)-1)*percent + 0.5)))]


def probe(detector, recognizer, image=None, iterations=3):
    report = {"model": "opencv-yunet-sface", "models": {"detector": inspect_model(detector), "recognizer": inspect_model(recognizer)}, "opencv": {"available": False}, "benchmark": {"status": "not_run"}}
    try:
        import cv2
        import numpy as np
    except ImportError:
        report['opencv']['reason'] = 'opencv_or_numpy_unavailable'
        return report
    report['opencv'] = {"available": True, "version": cv2.__version__, "face_detector_api": hasattr(cv2, 'FaceDetectorYN'), "face_recognizer_api": hasattr(cv2, 'FaceRecognizerSF')}
    if not all(v.get('ready') for v in report['models'].values()):
        report['benchmark']['status'] = 'model_unavailable'
        return report
    if not report['opencv']['face_detector_api'] or not report['opencv']['face_recognizer_api']:
        report['benchmark']['status'] = 'missing_opencv_apis'
        return report
    if image is None:
        report['benchmark']['status'] = 'no_consented_sample'
        return report
    try:
        data = Path(image).read_bytes()
        if not 4 <= len(data) <= 4 * 1024 * 1024:
            raise ValueError('image_size_out_of_bounds')
        from worker_protocol import read_burst
        from opencv_worker import extract
        # Only use JPEG inputs. Do not include paths, image bytes, embeddings, or faces in report.
        if data[:2] != b'\xff\xd8' or data[-2:] != b'\xff\xd9':
            raise ValueError('not_jpeg')
        read_burst(b'KONJE1\x01' + len(data).to_bytes(4,'little') + data)
        samples = []
        valid = 0
        for _ in range(iterations):
            start = time.perf_counter()
            outcome = extract([data], detector, recognizer)
            samples.append((time.perf_counter() - start)*1000)
            valid += outcome is not None
        status = "complete" if valid == iterations else ("incomplete_inference" if valid else "inference_no_embedding")
        report['benchmark'] = {"status": status, "runs": iterations, "embeddings_generated": valid, "p50_ms": round(statistics.median(samples),2), "p95_ms": round(percentile(samples,.95),2), "max_ms": round(max(samples),2), "measurement": "cold_model_init_plus_single_jpeg_inference"}
    except (OSError, ValueError, RuntimeError, cv2.error):
        # Fixed code only. No user path or exception strings.
        report['benchmark']['status'] = 'input_or_inference_error'
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--image', help='consented local JPEG for latency only; never copied')
    ap.add_argument('--runs', type=int, default=3)
    ap.add_argument('--out', help='optional JSON report (contains only model hashes and aggregate metrics)')
    args = ap.parse_args(argv)
    if not 1 <= args.runs <= 30:
        ap.error('--runs must be between 1 and 30')
    report = probe(os.getenv('KONJE_YUNET_MODEL'), os.getenv('KONJE_SFACE_MODEL'), args.image, args.runs)
    output = json.dumps(report, indent=2, sort_keys=True) + '\n'
    if args.out:
        path = Path(args.out)
        if path.exists():
            ap.error('refusing to overwrite existing report')
        fd = os.open(path, os.O_CREAT|os.O_EXCL|os.O_WRONLY, 0o600)
        with os.fdopen(fd, 'w') as file:
            file.write(output)
    else:
        sys.stdout.write(output)
    return 0 if report['benchmark']['status'] in ('complete','no_consented_sample') and all(v['ready'] for v in report['models'].values()) else 2


if __name__ == '__main__':
    raise SystemExit(main())