# Exact-model provisioning for KONJE (local evaluation only)

KONJE's OpenCV YuNet + SFace adapter is **an evaluation candidate, not validated clinical software**. It requires reviewed ONNX model weights; it never downloads them on its own during normal operation. Volunteers' images and face embeddings must stay out of Git.

## Model sources and checksums

| Artifact | Source | SHA-256 |
| --- | --- | --- |
| `face_detection_yunet_2023mar.onnx` | OpenCV's `opencv/opencv_zoo` organization mirror | `8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4` |
| `face_recognition_sface_2021dec.onnx` | OpenCV's `opencv/opencv_zoo` organization mirror | `0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79` |

Pinning verifies exact bytes, not licensing or recognition accuracy. The YuNet model directory indicates MIT terms; the SFace directory indicates Apache-2.0, but upstream training-data provenance and downstream commercial rights have been publicly questioned. Review these terms before real-world deployment: [YuNet source](https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet), [SFace source](https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface), [OpenCV Zoo SFace model-license inquiry](https://github.com/opencv/opencv_zoo/issues/313).

## Install and verify on an offline-capable Linux host

Install OpenCV 4.10+ from your OS package manager (on Debian 13: `python3-opencv python3-numpy`). Then **explicitly** allow model acquisition after reviewing the upstream terms:

```bash
python3 tools/provision_models.py --download --env-file "$HOME/.config/konje/model.env"
```

Downloads go only to the device's private model directory, use size limits and exact SHA-256 verification, and move into place after passing integrity checks. If a model file exists with an unexpected digest, provisioning fails rather than replacing it.

Load the generated model environment in the current shell, then check the model fingerprints and runtime availability:

```bash
source "$HOME/.config/konje/model.env"
python3 tools/model_preflight.py
```

**The model fingerprint now binds the exact reviewed `tools/opencv_worker.py` source bytes, detector and recognizer weight digests, and pipeline protocol version. Editing the worker—even its comments—invalidates earlier model IDs, so any enrolled identities must be re-enrolled after the model configuration is deliberately regenerated. This remains a consistency check, not a code-signature or runtime attestation.** To validate performance on the target Pi, the final stage requires consented local test images and measured false matches/abstentions. Do not use the generated example `.env` or these model hashes as evidence that real-world accuracy is adequate.

## Raspberry Pi 5 bootstrap

On Pi OS Debian 13 with the GitHub repository checked out:

```bash
cd ~/KONJE
bash scripts/bootstrap-pi.sh
# If you have reviewed the model terms and want exact research weights:
bash scripts/bootstrap-pi.sh --download-models
bash scripts/validate-pi.sh --diagnostics
```

The normal bootstrap builds and tests the C++ application and installs supported OpenCV CPU bindings. The `--download-models` option **must be explicitly chosen**. No command auto-enrolls people, creates encryption keys, captures camera images, or asserts identity accuracy.
## Offline threshold calibration (after Pi capture and consent)

The repository includes a **model-scoped experimental evaluator**, not a production-ready threshold. Do not use the hard-coded cosine threshold to announce real identities without measuring false accepts and false rejects. Keep identifying information, image buffers, and embeddings outside GitHub. Generate two de-identified CSV files for disjoint capture **sessions**:

```text
truth_id,best_id,best_similarity,second_similarity
a,a,0.88,0.21
,b,0.39,0.12
```

An empty `truth_id` means an unknown person. An empty `best_id` means the worker declined to choose a candidate. `-2` is the existing C++ no-runner-up sentinel. The columns record actual measured similarity scores; do not fabricate them.

```bash
source "$HOME/.config/konje/model.env"
python3 tools/calibrate_policy.py /private/dev-scores.csv /private/holdout-scores.csv \
  --model-id "$KONJE_MODEL_ID" --max-wrong-accepts 0 --out /private/calibration-report.json
```

The tool chooses on the development split only, evaluates once on independent holdout data, and reports a Wilson 95% upper bound under independent-binomial assumptions. Small samples, correlated attempts, leakage across sessions, and unsafe model licenses can make these estimates misleading. This tool **never** edits the runtime policy or enrolled profiles; manual review and actual device testing are required. 
