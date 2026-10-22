# KONJE persistent inference and controlled image benchmarking

**Status:** experimental; no physical Pi inference, accuracy, or acceptable false-match rate has been established by this code alone.

## Persistent worker

- `tools/persistent_worker.py` loads pinned YuNet + SFace ONNX weights **once** at startup and listens on a Unix domain socket.
- `src/persistent_client.cpp` connects from the C++ application with a bounded, deadline-aware request that carries a model-space identifier and a `KONJE1` JPEG burst. The response is an embedding or `UNCERTAIN`, never a person's name.
- The worker serializes inference; the kernel listen backlog is **2**. This limits queued connections but does not replace admission control and load testing. The existing C++ scheduler already coalesces pending requests.
- The socket is created mode 0600 in an owner-only directory; the C++ client validates ownership and permissions. No network listener or photo/embedding files are created.
- Disconnected, invalid, mismatched, or timed-out workers fail closed. Cancellation ends client waiting but **does not currently preempt an in-progress OpenCV inference**; the server may finish the abandoned request before serving the next one.
- An operator or systemd supervisor must restart a crashed worker. The server deliberately refuses to replace an existing socket path; remove stale sockets only after ensuring no worker is still running.
- If `KONJE_WORKER_SOCKET` is unset, the original single-shot `KONJE_WORKER_PATH` flow remains available.

### Pi-side manual startup (after hardware and model setup)

In one SSH terminal:

```bash
cd ~/KONJE
source "$HOME/.config/konje/model.env" # contains reviewed weight paths/hashes and KONJE_MODEL_ID
install -d -m 700 "$HOME/.local/share/konje/run"
python3 tools/persistent_worker.py --socket "$HOME/.local/share/konje/run/worker.sock"
```

In a *second* SSH terminal (same model.env):

```bash
cd ~/KONJE
source "$HOME/.config/konje/model.env"
export KONJE_WORKER_SOCKET="$HOME/.local/share/konje/run/worker.sock"
export KONJE_CAMERA=none   # change only after verifying actual camera hardware
export KONJE_SPEECH=off
cmake -S . -B build -G Ninja
cmake --build build -j2
ctest --test-dir build --output-on-failure
./build/konje init-key  # first time only; never publish this key
./build/konje run
```

`KONJE_CAMERA=none` yields an expected unavailable response, not a device endorsement. To run the full interaction requires a verified camera, reviewed models, calibrated policy and consented enrollment. **Do not enable spoken identities for research-dataset subjects.**

## Research image benchmarks

Use a *locally provisioned and authorized* dataset with existing ground-truth identity labels. Do **not** scrape, auto-label, or publish arbitrary online celebrity images. Recommended research candidates:

- [CelebA official project](https://mmlab.ie.cuhk.edu.hk/projects/CelebA.html): 202,599 images across 10,177 identities, diverse pose conditions. **Noncommercial research only**, no redistribution of images or derived data; obtain and review terms yourself.
- [QLFW official dataset](https://ivulab.asu.edu/databases/qlfw): impaired/quality-labelled face images, with evaluation protocols for degradations. Check relevant terms and protocol.
- [OpenCV Zoo](https://github.com/opencv/opencv_zoo): source of YuNet/SFace model specifications. A public discussion of SFace weight training-data provenance is not yet resolved; do not assume downstream commercial or clinical clearance.

The benchmark requires a CSV next to your local JPEGs:

```csv
path,identity,role,pose
data/person_001/front_train.jpg,person_001,enroll,frontal
data/person_001/side_dev.jpg,person_001,dev_known,left_profile
data/person_001/front_test.jpg,person_001,holdout_known,frontal
data/person_999/unknown_dev.jpg,person_999,dev_unknown,unspecified
data/person_998/unknown_test.jpg,person_998,holdout_unknown,unspecified
```

The example is **illustrative, incomplete**: supply multiple known and unknown identities, genuine held-out images, and independent sessions where possible. `identity` values should be opaque ground-truth labels, not names. Use roles `enroll`, `dev_known`, `dev_unknown`, `holdout_known`, `holdout_unknown`. The evaluator requires disjoint unknown identities between development and holdout and forbids duplicate paths. `pose` is **ground-truth metadata**, never guessed from an image; use `unspecified` if not annotated.

```bash
source "$HOME/.config/konje/model.env"
python3 tools/benchmark_faces.py \
  --manifest /private/research/manifest.csv \
  --out /private/research/benchmark-report.json
```

For each query, the runner tests Gaussian blur `sigma=0`, `1.5` and `3.0` (synthetic augmentation), calculates embedding latency from a preloaded CPU model, tunes threshold and margin on the **development** set only, then reports wrong accepts and abstentions on holdout by blur and pose. `sigma=3.0` is **not** a replacement for naturally motion-blurred images. Use actual front/profile examples to measure viewpoint robustness; rotated frontal photos do not simulate profile views. The JSON report contains aggregate statistics only, not image bytes, paths, individual identities, or embeddings.

These statistics are **not a validated safety guarantee**, especially for correlated augmentations and small samples. In particular, *zero observed false accepts does not mean zero false accept probability.* Use sufficiently large independent test cohorts and appropriate privacy/license review before enrolling real volunteers. Never use the same images or identities labelled as unknown in both calibration and final evaluation, and do not retune against the holdout outcomes.

## What can be signed off by CI

- Native C++ ↔ Python wire protocol, model-ID mismatch behavior, request bounds and clean shutdown use **synthetic data**.
- Python tests check manifest split validation, score-based policy selection and blur grouping logic without private images.
- x86/ARM64 build and sanitizer tests exercise software only.

## Still required on Pi

Actual weight licensing/provisioning, repeatable CPU p50/p95/p99 and RSS measurement, cold-vs-warm comparison, camera/speaker and power-cycle behavior, model restart after crash, sustained multi-hour soak testing, measured false-accept rate on independent consenting people, and revocation tests during active speech.

### Optional real-public-figure research run (GitHub Actions)

The opt-in research workflow `.github/workflows/research-faces.yml` downloads checksum-pinned **LFW funneled** images into the ephemeral GitHub runner. The SHA-256 digest is the exact scikit-learn upstream LFW funneled archive checksum. It anonymizes image identity labels internally, uses disjoint unknown-person development and holdout groups, and reports aggregates by blur; it does not print identities, upload JPEGs, or upload embeddings. It is triggered by changes to that workflow or via manual `workflow_dispatch`, not by every application commit. Model weights are also checksum-pinned. If the source server is inaccessible, the job fails without claiming a benchmark result.

LFW images contain varying natural viewpoints but no ground-truth pose annotations in this workflow; all `pose` fields remain `unspecified`. For **verified frontal/profile conditions**, an appropriately licensed dataset with explicit pose annotations (such as CFP-FP) or consenting volunteers must be supplied separately.