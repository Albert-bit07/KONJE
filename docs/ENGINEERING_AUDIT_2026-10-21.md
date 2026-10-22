# KONJE Engineering Audit — 2026-10-21

**Scope:** Linux C++20 runtime, subprocess management, request lifecycle, encrypted profile storage, local face-model adapters, calibration tooling, automated tests, deployment diagnostics and GitHub Actions. This report distinguishes tested software from hardware and biometric accuracy that have not been measured.

## Evidence from this audit

- Source baseline: private `Albert-bit07/KONJE`, main branch; [latest green CI run #43](https://github.com/Albert-bit07/KONJE/actions/runs/39701749766) at `3425fc01`.
- CI jobs: `core` (build, four CTest suites, Python unit tests, Python syntax + Bash syntax) and `sanitizers` (ASan/UBSan instrumented build with repeated core and mock pipeline tests), both successful.
- Initial local subprocess regression: capturing 262,144 bytes with `head -c 262144 /dev/zero` produced **65,536 bytes and exit code 1**, five times, because both pipe ends were set nonblocking. After changing only the parent read end to nonblocking, the same reproduction returned **262,144 bytes and exit code 0**, five times. A 256-KiB regression test now runs in CI.
- Verified in-flight cancellation is covered by a new C++ test; encrypted profile round trips now assert model identity persists.
- Simulated camera/worker/speech tests use **fake JPEG data, embeddings and a fake TTS executable**. They are not recognition-accuracy or physical-hardware tests.

## Repairs

| Area | Severity | Change | Evidence |
| --- | --- | --- | --- |
| Child subprocess stdout marked nonblocking | High: can truncate JPEG captures or inference output | Make only parent pipe read nonblocking; preserve blocking stdout for child | Local reproduction before/after; GitHub CI regression |
| Over-limit child stdout after wrapper exited | Medium: possible orphan descendants | Terminate child process group on output overflow | Source inspection, sanitizer CI; no dedicated orphan-process test yet |
| Model preflight reported 'complete' despite failed embeddings | Medium: misleading model readiness | Distinguish complete, partial and zero embedding outcomes; return non-success | Python regression tests, CI |
| Calibration accepted empty identity and invalid score settings | Medium: distorted error-rate estimates | Require a nonempty candidate ID, validate thresholds/similarity range and align no-runner-up sentinel with C++ | Python regression tests, CI |
| Only basic CI | Medium: latent memory defects | Add ASan/UBSan CI job and repeated integration tests | GitHub Actions core + sanitizer success |
| Device validation undocumented | Operational | Add `scripts/validate-pi.sh`; diagnostic mode does not capture faces or generate keys | CI Bash syntax; not executed on Pi |

## Reproducibility

```bash
cmake -S . -B build -G Ninja -DCMAKE_BUILD_TYPE=Debug
cmake --build build --parallel 2
ctest --test-dir build --output-on-failure --timeout 45
python3 -m unittest discover -s tools -p 'test_*.py' -v
bash scripts/validate-pi.sh
```

On the actual Pi, `bash scripts/validate-pi.sh --diagnostics` additionally lists cameras/audio and runs model preflight **without taking photos**. The software tests and optional model checks must be run on ARM64 before device sign-off.

## Outstanding release blockers

1. **Camera and speaker:** Earlier Raspberry Pi 5 diagnostics returned no camera and only HDMI audio outputs. Need a confirmed compatible camera, audible speaker, PSU headroom, and measured capture-to-announcement behavior.
2. **Model licensing and actual inference:** No approved YuNet/SFace ONNX weights have been provisioned/benchmarked here. Local workers' fail-closed behavior is tested, but model correctness and ARM64 compatibility remain unverified.
3. **Recognition safety:** The 0.60 score and 0.10 margin are **experimental defaults**, not calibrated probabilities or medically appropriate guarantees. Use consented positives/negatives, bystander samples, lighting variants, known unknowns, multi-person frames and uncertainty metrics; set acceptance criteria before enabling real identity announcements.
4. **Operational reliability:** No persistent worker, service supervisor, camera recovery trials, power-cycle test, or 24h soak test. Validate cancellation of running hardware and TTS, power-loss recovery, flash wear, and resource usage.
5. **Biometric/privacy threat model:** A database encrypted with a key stored on the same microSD card is not sufficient protection against physical theft. Swap, core dumps and filesystem backups may persist transient images. Real enrollment requires controlled key storage, consent proof, authenticated profile editing, data deletion policy and approved retention.
6. **Revocation race:** Matching rechecks the local database before speech, but the implementation does not enforce a global revocation barrier across offline devices or guarantee interruption of a speech operation already underway.
7. **Other architecture concerns:** Worker reloads ONNX models for every request, so cold-start overhead can dominate Pi latency. Assess persistent worker with bounded queue, health checks and model-version negotiation only after a measured baseline.

## Scope limits

Green GitHub Actions means the Linux code and mocked workflows pass on hosted runner hardware. It **does not** mean a full KONJE wearable, caregiver workflow, clinical application or real-world face-identification experience has passed end-to-end validation. No volunteer imagery, face embeddings, encryption keys or pretrained model binaries are committed to this repository.
