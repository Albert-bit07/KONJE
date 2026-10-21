# Known hardware state (from interactive SSH diagnostics, 2026-10-21)

- Raspberry Pi 5 Model B Rev 1.1, 8 GB physical RAM (7.9 GiB reported), Debian 13 (trixie), aarch64.
- GCC 14.2, CMake 3.31.6, Ninja 1.12.1, Git 2.47 installed by the user.
- `rpicam-hello --list-cameras` returned "No cameras available!".
- `aplay -l` listed HDMI0/HDMI1 only; no verified audible speaker.
- USB-C Dell 65W laptop adapter supports 5V/3A; use official 5.1V/5A 27W Pi PSU when adding peripherals.
- SSH worked through iPhone hotspot at hostname `konje.local`.

**Important distinction:** the previous Pi compilation tested only a *minimal two-request demonstration* (`main.cpp` with a constant camera-unavailable message). The architecture here is an expanded, separate GitHub-source draft; it has NOT been built or run on the Pi. Its initial CI/host tests run on Linux x86-64 only. No camera capture, audio playback or real identity recognition has been verified.