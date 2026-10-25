#!/usr/bin/env bash
# One command to set up (first time only) and start KONJE, on a Mac or a Raspberry Pi.
set -e
cd "$(dirname "$0")"
if [ ! -d .venv ]; then
  echo "First run: installing libraries (takes a few minutes)..."
  python3 -m venv .venv
  .venv/bin/pip install --upgrade pip -q
  .venv/bin/pip install -r requirements.txt -q
fi
.venv/bin/python download_models.py
.venv/bin/python run.py
