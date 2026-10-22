#!/usr/bin/env bash
# One-time KONJE Pi 5 setup. Safe to rerun; does not enroll anyone or overwrite keys.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

DOWNLOAD_MODELS=false
case "${1:-}" in
    "") ;;
    --download-models) DOWNLOAD_MODELS=true ;;
    *) echo "Usage: bash scripts/bootstrap-pi.sh [--download-models]" >&2; exit 2 ;;
esac

if [[ "$(uname -s)" != Linux ]]; then
    echo "KONJE requires Linux (Raspberry Pi OS preferred)." >&2
    exit 2
fi

if [[ "$(uname -m)" != aarch64 ]]; then
    echo "Warning: development host is $(uname -m), not Raspberry Pi ARM64." >&2
fi

echo "Installing system build, camera and local inference prerequisites..."
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
    build-essential cmake ninja-build git pkg-config libssl-dev libsqlite3-dev \
    python3 python3-numpy python3-opencv python3-venv ffmpeg espeak-ng alsa-utils

echo "Verifying OpenCV APIs..."
python3 - <<'PY'
import cv2
import numpy
assert hasattr(cv2, 'FaceDetectorYN'), 'Missing OpenCV FaceDetectorYN'
assert hasattr(cv2, 'FaceRecognizerSF'), 'Missing OpenCV FaceRecognizerSF'
print('OpenCV', cv2.__version__, 'NumPy', numpy.__version__)
PY

echo "Compiling and testing KONJE native software..."
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Release
cmake --build build --parallel 2
ctest --test-dir build --output-on-failure --timeout 45
python3 -m unittest discover -s tools -p 'test_*.py' -v

if [[ "$DOWNLOAD_MODELS" = true ]]; then
    echo "Fetching only verified model weights for research evaluation."
    echo "Commercial rights and training-data provenance require separate review."
    envfile="$HOME/.config/konje/model.env"
    if [[ -e "$envfile" ]]; then
        echo "Model environment file already exists; refusing overwrite: $envfile" >&2
        echo "To verify existing weights: python3 tools/provision_models.py" >&2
    else
        python3 tools/provision_models.py --download --env-file "$envfile"
    fi
fi

envfile="$HOME/.config/konje/model.env"
if [[ -r "$envfile" ]]; then
    # shellcheck disable=SC1090
    source "$envfile"
    echo "Running pinned-model synthetic inference smoke..."
    python3 tools/model_smoke.py
    python3 tools/synthetic_worker_smoke.py
else
    echo "[PENDING] Verified model environment not installed; use --download-models after license review."
fi

echo "[PASS] C++ build, simulated end-to-end tests and OpenCV APIs on this host."
echo "[NOT TESTED] Real camera, audible speech, recognition accuracy and Pi-specific latency."
echo "Next: bash scripts/validate-pi.sh --diagnostics"