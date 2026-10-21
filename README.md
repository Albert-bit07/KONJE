# KONJE — Keeping Our Names, Journeys, and Experiences

**On-request, consent-first memory-assistance prototype for a Raspberry Pi 5.** The project is named after the founder's mother. It develops ideas from [See Through](https://github.com/A2Hackathon/see-through), a collaborative HopHacks 2026 project by Albert Mejooli and Amanda Le. Attribution and reuse boundaries: [ATTRIBUTION.md](ATTRIBUTION.md).

> **Experimental, not medical software.** No established clinical benefit, verified recognition accuracy, reliable safety alerts, or independence outcome. A false identification could be harmful. Do not rely on KONJE for medical decisions or emergencies.

## What exists today

A single C++20 executable with modular components for bounded on-request camera capture, cancellation, a privacy-preserving inference adapter, encrypted profiles, conservative recognition policy, and offline speech. The optional Python worker is restricted to extracting face embeddings; it never receives the encrypted directory or decides what relationship to announce. No always-on recording, cloud service, caregiver API, location tracking, medication or fall detection is implemented.

**Differences from See Through:** no plaintext embedding database, no raw debug images, no automatic generative relationship summaries, no continuous camera monitoring, and no multi-service network deployment during the tabletop stage. The Pi 5 owns the policy; the camera sends at most three JPEGs per request to a single local worker through a bounded memory-only IPC envelope. The worker picks the sharpest usable frame before attempting matching. The C++ application owns final selection and announcement.

## Current verification

| Area | Status |
|---|---|
| Raspberry Pi 5 (8 GB), Debian 13, SSH, GCC/CMake/Ninja | Verified by user in Pi terminal |
| Earlier, minimal `main.cpp` on Pi | Built and executed by user |
| **This expanded repository** C++ build + unit tests | Validated on Linux x86-64 in assistant environment |
| Mocked capture → embedding → encrypted match → approved speech → revocation | Software simulation passed, no real images/audio |
| Expanded app built on Pi / real camera / real speaker / real model | **Not verified** |
| Latency, identification error rates, privacy efficacy, clinical benefit | **Not measured** |

## Linux/Pi build

```bash
bash scripts/setup-pi.sh
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug
cmake --build build
ctest --test-dir build --output-on-failure
./build/konje --help
```

`setup-pi.sh` installs `build-essential cmake ninja-build git pkg-config libssl-dev libsqlite3-dev python3 python3-venv`. Enable camera/audio utilities separately once the hardware is available.

## Safe first run (no camera yet)

```bash
./build/konje init-key
./build/konje run
```

`Enter` creates a request, `c` cancels the latest request, `q` stops. With no worker/camera configured, the program reports unavailable; **it never invents a person**.

- Key file: `~/.config/konje/master.key`, owner-only 0600; created explicitly once with `init-key`.
- Encrypted SQLite: `~/.local/share/konje/profiles.sqlite3`; owner-only 0600.
- **Warning:** If both key and DB are on the same microSD card, encryption does not protect against physical extraction of both. A separate secure-key scheme is needed before real deployment. Protect/back up your key; never commit it.

## Hardware and model adapter (opt in only)

The Pi's last diagnostic said **no camera**, and only HDMI audio outputs were listed. Wait until camera/speaker hardware is connected. With a CSI Pi camera and `rpicam-still` available:

```bash
export KONJE_CAMERA=rpicam
# Or for a USB UVC camera with ffmpeg installed:
# export KONJE_CAMERA=uvc
# export KONJE_UVC_DEVICE=/dev/video0

# Confirm the chosen pretrained model license and ARM64 CPU compatibility first.
export KONJE_WORKER_PATH="$PWD/tools/recognition_worker.py"
export KONJE_MODEL_ROOT="$HOME/.local/share/konje-models"
export KONJE_MODEL_PACK="your_installed_licensed_pack"

# Only enable speech after espeak-ng and an audible output device are working:
export KONJE_SPEECH=on
./build/konje run
```

The worker **does not ship with weights** and refuses to run unless an explicitly installed model pack exists. InsightFace's pretrained `buffalo_l` weights have restricted model-use terms; package/model permissions must be reviewed separately. Do not publish model weights or assume Pi-native ONNX/InsightFace packages are available. See [docs/MODEL_SETUP.md](docs/MODEL_SETUP.md).

### Consent-based enrollment

Once real hardware and a permitted worker are ready, conduct a supervised tabletop session with **three consenting volunteers**, one at a time:

```bash
./build/konje enroll volunteer_001
# Type CONSENT CONFIRMED, approved name, approved relationship,
# exact approved introduction, then press Enter for each of 3 camera captures.
./build/konje list              # Lists opaque IDs only
./build/konje revoke volunteer_001
```

Enrollment requires three separate frames and a consistent embedding. Thresholds for both enrollment consistency and identification are **development heuristics, not calibrated recognition probabilities**. Profiles are encrypted by default; local revoke deletes them from the active database, but SD backups and a future offline replica may still retain data. No live clinical/wearer deployment is authorized by this prototype.

## Codebase

```text
CMakeLists.txt, .github/workflows/ci.yml
include/konje/                C++ interfaces
src/main.cpp                 Enroll/revoke/list/run CLI
src/scheduler.cpp            Latest-request-wins; bounded pending queue
src/process.cpp              Linux cancellable subprocess, memfd data passing
src/pipeline.cpp             Camera burst -> embedding -> policy -> speech
src/policy.cpp               Similarity and margin abstention
src/profile_store.cpp        Authenticated encryption and SQLite persistence
tools/recognition_worker.py  Optional local CPU inference adapter
 tools/worker_protocol.py    Versioned 1-3 JPEG binary IPC decoder
 tools/evaluate_policy.py   Evaluate de-identified matching scores
tests/                       Unit and simulated end-to-end tests
scripts/setup-pi.sh          Native build prerequisites
scripts/deploy-pi.ps1        Windows-to-Pi source deployment
docs/                        Architecture/security/hardware/model setup
```

`reference/see-through/` from the earlier sparse import is **not part of this repository**. No original See Through code was copied into `src` or `tools`.

## Distributed systems roadmap — not implemented

After a reliable local session, add secure caregiver versioned sync, offline reconciliation, idempotent updates, durable applied-version acknowledgements, expiry, tombstones and explicit offline revocation status. Review the [failure/recovery contract](docs/ARCHITECTURE.md) before adding a server. Do not split into microservices to manufacture complexity.

**Deployment:** From Windows PowerShell in this repository run `./scripts/deploy-pi.ps1`; it transfers only code, not biometrics or keys. Build and run the tests on the Pi afterward. Keep your GitHub repository private until upstream attribution and model licenses are clear.