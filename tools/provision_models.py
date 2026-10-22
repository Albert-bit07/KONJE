#!/usr/bin/env python3
"""Explicit, checksum-pinned OpenCV model provisioner for local evaluation.

Network is disabled by default. Run --download only after reviewing model rights.
No volunteer data, embeddings, keys, or model weights are committed to Git.
"""
from __future__ import annotations

import argparse
import hashlib
import os
from pathlib import Path
import shlex
import stat
import tempfile
from typing import NamedTuple
from urllib.request import urlopen

from model_identity import fingerprint


class Model(NamedTuple):
    filename: str
    url: str
    sha256: str
    maximum_bytes: int


# Immutable exact weight bytes (SHA-256 from the original OpenCV Zoo model assets).
# The official OpenCV organization hosts this mirrored model collection.
SPECS = (
    Model("face_detection_yunet_2023mar.onnx",
          "https://huggingface.co/opencv/opencv_zoo/resolve/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx",
          "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4", 2 * 1024 * 1024),
    Model("face_recognition_sface_2021dec.onnx",
          "https://huggingface.co/opencv/opencv_zoo/resolve/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx",
          "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79", 48 * 1024 * 1024),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def validate(path: Path, spec: Model) -> bool:
    if path.is_symlink() or not path.is_file():
        return False
    size = path.stat().st_size
    return 0 < size <= spec.maximum_bytes and sha256(path) == spec.sha256


def fetch_verified(spec: Model, directory: Path, opener=urlopen) -> Path:
    """Download to a private temporary file, verify, then atomically install."""
    destination = directory / spec.filename
    if validate(destination, spec):
        return destination
    if destination.exists() or destination.is_symlink():
        raise ValueError(f"Refusing to overwrite invalid existing model: {spec.filename}")
    fd, raw_path = tempfile.mkstemp(prefix=".download-", suffix=".part", dir=directory)
    tmp = Path(raw_path)
    try:
        total = 0
        digest = hashlib.sha256()
        with os.fdopen(fd, "wb") as output, opener(spec.url, timeout=45) as incoming:
            while True:
                chunk = incoming.read(1024 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > spec.maximum_bytes:
                    raise ValueError("Downloaded model exceeds size bound")
                digest.update(chunk)
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
        if total == 0 or digest.hexdigest() != spec.sha256:
            raise ValueError(f"Checksum mismatch: {spec.filename}")
        # Prevent accidentally replacing a newly-created file from another run.
        if destination.exists() or destination.is_symlink():
            raise ValueError(f"Model installed concurrently: {spec.filename}")
        os.chmod(tmp, stat.S_IRUSR | stat.S_IWUSR)
        os.replace(tmp, destination)
        return destination
    finally:
        tmp.unlink(missing_ok=True)


def render_env(paths: tuple[Path, Path]) -> str:
    detector, recognizer = paths
    values = {
        "KONJE_YUNET_MODEL": str(detector.resolve()),
        "KONJE_SFACE_MODEL": str(recognizer.resolve()),
        "KONJE_YUNET_SHA256": SPECS[0].sha256,
        "KONJE_SFACE_SHA256": SPECS[1].sha256,
        "KONJE_MODEL_ID": fingerprint(detector, recognizer),
    }
    return "".join(f"export {key}={shlex.quote(value)}\n" for key, value in values.items())


def provision(directory: Path, download: bool) -> str:
    directory = directory.expanduser().absolute()
    if directory.is_symlink():
        raise ValueError("Model directory cannot be a symlink")
    directory.mkdir(parents=True, mode=0o700, exist_ok=True)
    if not directory.is_dir():
        raise ValueError("Model directory must be a regular directory")
    paths = []
    for spec in SPECS:
        path = directory / spec.filename
        if download and not validate(path, spec):
            fetch_verified(spec, directory)
        if not validate(path, spec):
            raise ValueError(f"Model unavailable or checksum mismatch: {spec.filename}; use --download after license review")
        paths.append(path)
    return render_env((paths[0], paths[1]))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--models-dir", type=Path, default=Path.home() / ".local/share/konje/models")
    parser.add_argument("--download", action="store_true", help="explicitly fetch official exact-checksum evaluation weights")
    parser.add_argument("--env-file", type=Path, help="write shell exports in a private NEW file (never overwrite)")
    args = parser.parse_args(argv)
    try:
        content = provision(args.models_dir, args.download)
        if args.env_file:
            target = args.env_file.expanduser()
            target.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
            with os.fdopen(os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600), "w") as fp:
                fp.write(content)
            print(f"Verified models. Source local environment file: {target}")
        else:
            print(content, end="")
        return 0
    except (OSError, ValueError) as error:
        parser.exit(2, f"Model provisioning unavailable: {error}\n")


if __name__ == "__main__":
    raise SystemExit(main())