# Known hardware state (from interactive SSH diagnostics, 2026-10-21)

- Raspberry Pi 5 Model B Rev 1.1, 8 GB physical RAM (7.9 GiB reported), Debian 13 (trixie), aarch64.
- GCC 14.2, CMake 3.31.6, Ninja 1.12.1, Git 2.47 installed by the user.
- `rpicam-hello --list-cameras` returned "No cameras available!".
- `aplay -l` listed HDMI0/HDMI1 only; no verified audible speaker.
- USB-C Dell 65W laptop adapter supports 5V/3A; use official 5.1V/5A 27W Pi PSU when adding peripherals.
- SSH worked through iPhone hotspot at hostname `konje.local`.

**Important distinction:** the previous Pi compilation tested only a *minimal two-request demonstration* (`main.cpp` with a constant camera-unavailable message). The architecture here is an expanded, separate GitHub-source draft; it has NOT been built or run on the Pi. Its initial CI/host tests run on Linux x86-64 only. No camera capture, audio playback or real identity recognition has been verified.
## Reproducible deployment-stage checks

Once the private repository has been cloned to the Pi and the dependencies in `scripts/setup-pi.sh` are installed, run:

```bash
cd ~/KONJE
bash scripts/validate-pi.sh
bash scripts/validate-pi.sh --diagnostics
```

The first command builds the full C++20 application on the host and runs the C++ mock integration tests and Python unit tests. The second also **lists** camera/audio devices and checks local ONNX readiness without capturing images, producing speech, enrolling anyone or changing cryptographic keys. The printed "[PASS]" pertains to software tests only, **not** real-model accuracy or camera-to-speaker operation.

Before real volunteer testing, separately verify the camera, speaker, appropriately licensed model weights, matching thresholds, consent and revocation process, and actual device latency. Model preflight only measures latency if explicitly passed a consented local JPEG.

Privacy caveats: local AES-GCM profile encryption does not protect against theft of both the database **and** the encryption key stored on the same microSD card. Unencrypted swap, filesystem snapshots, crash dumps and backups can also undermine a claim that raw frames never reach persistent storage. An unattended deployment needs a documented key-handling threat model and privacy controls before real personal data is enrolled.
