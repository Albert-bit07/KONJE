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

**The model fingerprint ties weights to the declared preprocessing protocol version but is not a code-signature or code-integrity attestation.** To validate performance on the target Pi, the final stage requires consented local test images and measured false matches/abstentions. Do not use the generated example `.env` or these model hashes as evidence that real-world accuracy is adequate.

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