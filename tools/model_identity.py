"""Local-only SHA-256 model identity and integrity checks. Never downloads weights."""
import hashlib
import os
from pathlib import Path

CHUNK_SIZE = 1024 * 1024
PIPELINE_VERSION = "yunet-sface-opencv-v1"


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(CHUNK_SIZE), b""):
            digest.update(chunk)
    return digest.hexdigest()


def fingerprint(detector, recognizer):
    """Bind detector and recognizer bytes plus preprocessing implementation version."""
    h = hashlib.sha256()
    for part in (PIPELINE_VERSION, sha256_file(detector), sha256_file(recognizer)):
        h.update(part.encode("ascii"))
        h.update(b"\0")
    return "opencv-sface-" + h.hexdigest()


def verified_paths(env=None):
    """Fail closed unless configured digests equal model bytes at call time."""
    if env is None:
        env = os.environ
    detector = env.get("KONJE_YUNET_MODEL", "")
    recognizer = env.get("KONJE_SFACE_MODEL", "")
    expected_detector = env.get("KONJE_YUNET_SHA256", "").lower()
    expected_recognizer = env.get("KONJE_SFACE_SHA256", "").lower()
    expected_identity = env.get("KONJE_MODEL_ID", "")
    if not all((detector, recognizer, expected_detector, expected_recognizer, expected_identity)):
        return None
    if any(len(value) != 64 or any(c not in "0123456789abcdef" for c in value)
           for value in (expected_detector, expected_recognizer)):
        return None
    paths = (Path(detector), Path(recognizer))
    try:
        if not all(p.is_file() and p.suffix.lower() == ".onnx" for p in paths):
            return None
        if sha256_file(paths[0]) != expected_detector or sha256_file(paths[1]) != expected_recognizer:
            return None
        if fingerprint(*paths) != expected_identity:
            return None
    except OSError:
        return None
    return paths

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Print identity for reviewed local ONNX model files")
    parser.add_argument("detector")
    parser.add_argument("recognizer")
    args = parser.parse_args()
    print("export KONJE_YUNET_SHA256=" + sha256_file(args.detector))
    print("export KONJE_SFACE_SHA256=" + sha256_file(args.recognizer))
    print("export KONJE_MODEL_ID=" + fingerprint(args.detector, args.recognizer))
