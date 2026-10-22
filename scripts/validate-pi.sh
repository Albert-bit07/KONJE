#!/usr/bin/env bash
# Reproducible software validation on Raspberry Pi OS or ordinary Linux.
# Never captures real faces, enrolls volunteers, or changes local encryption keys.
set -euo pipefail

usage() {
    echo "Usage: bash scripts/validate-pi.sh [--diagnostics]" >&2
    exit 2
}
if (( $# > 1 )); then usage; fi
if (( $# == 1 )) && [[ "$1" != "--diagnostics" ]]; then usage; fi

repo_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
echo "=== KONJE software validation ==="
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    echo "Source revision: $(git rev-parse --short HEAD)"
fi
echo "Architecture: $(uname -m)"
cmake -S . -B build-validation -G Ninja -DCMAKE_BUILD_TYPE=Debug
cmake --build build-validation --parallel 2
ctest --test-dir build-validation --output-on-failure --timeout 45
python3 -m unittest discover -s tools -p 'test_*.py' -v
python3 -m compileall -q tools tests
echo "[PASS] Linux software, tests and Python syntax."

if (( $# == 0 )); then
    echo "Device I/O, ONNX inference and volunteer recognition are NOT verified by these tests."
    exit 0
fi

echo "=== Hardware and model diagnostics (no capture) ==="
if [[ -r /proc/device-tree/model ]]; then
    tr -d '\000' < /proc/device-tree/model
    echo
fi
if command -v rpicam-hello >/dev/null 2>&1; then
    rpicam-hello --list-cameras || true
else
    echo "[PENDING] rpicam-hello is unavailable; this does not rule out a USB webcam."
fi
if command -v aplay >/dev/null 2>&1; then
    aplay -l || true
else
    echo "[PENDING] ALSA audio listing is unavailable."
fi
python3 tools/model_preflight.py || echo "[PENDING] Models or runtime unavailable; see docs/OPENCV_MODEL_CANDIDATE.md."
echo "Camera capture, audible speech, real-model inference and calibrated face recognition require separate hands-on tests."
