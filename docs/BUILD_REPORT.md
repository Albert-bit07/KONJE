# KONJE local validation report — 2026-10-21

### Verified in an isolated Linux x86-64 environment

- C++20 project configured with CMake and Ninja using GCC 14.2; linked against OpenSSL, SQLite and pthreads.
- `cmake --build build` succeeded.
- `ctest --test-dir build --output-on-failure` completed: **4/4 passing** (`konje_core_tests`, `konje_help`, `burst_worker_protocol`, `mock_full_pipeline`).
- `python3 -m unittest discover -s tools -p 'test_*.py' -v` completed: **3/3 passing**.
- Python syntax compilation passed for the shipped worker and evaluation utilities.

### Simulated behavior tested

- Consent attestation + 3 synthetic in-memory capture frames + synthetic embeddings → encrypted profile persistence.
- Synthetic request → capture burst → model adapter → C++ policy → fake local speaker receives only exact stored approved text.
- Profile revocation → subsequent synthetic request abstains and makes no speech call.
- Stale request replacement, bounded child process output, cancellation, timeout, corrupted ciphertext authentication failure, unknown identity and near-tie cases.

### Not tested / not claimed

- This new repository's binaries on the Raspberry Pi 5; real Pi CSI/USB camera; real audio output.
- Model weights licensing, ARM64 InsightFace/ONNX compatibility, real face embeddings, false-accept rates, liveness, clinical benefit, latency or recovery from real power loss.
- Durable caregiver update ledger/ACKs and offline synchronization (future work).

Mock tests are **not** biometric accuracy tests. Their fake vectors and fake JPEG marker bytes must not be used as enrolled people or real measurement data.