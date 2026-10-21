#!/usr/bin/env bash
set -euo pipefail

if [[ "$(uname -m)" != "aarch64" ]]; then
    echo "Warning: this script was written for a 64-bit Raspberry Pi; detected $(uname -m)." >&2
fi
sudo apt update
sudo apt install -y build-essential cmake ninja-build git pkg-config libssl-dev libsqlite3-dev python3 python3-venv

echo "Build dependencies installed. For audio: sudo apt install espeak-ng"
echo "For a USB camera, install ffmpeg; for CSI use your distro's rpicam-apps."
echo "Model/ONNX runtime setup is deliberately manual until Pi compatibility and licensing are verified."
echo "Next: cmake -S . -B build -G Ninja && cmake --build build && ctest --test-dir build --output-on-failure"