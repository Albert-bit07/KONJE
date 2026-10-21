# Optional research embedding worker (NOT deployed/tested on Pi)

The C++ application works and tests without ML dependencies. `tools/recognition_worker.py` is a contract for a local CPU extractor, not a committed pretrained model.

**Before enabling it:**

1. Confirm device camera (`rpicam-hello --list-cameras` or `ls /dev/video*`) and an audible speaker separately. CSI requires `rpicam-still`; USB UVC requires `ffmpeg`.
2. Research and verify a pretrained face model with legal rights for the intended use. InsightFace libraries and pretrained weights can carry different licenses; commonly used `buffalo_l` pretrained weights are not cleared for commercial use. No weights are provided in Git.
3. Test ARM64 wheels for Debian 13: `numpy`, `opencv-python` or `python3-opencv`, `insightface`, and CPU-compatible `onnxruntime`. Nothing in this repository assumes these have already been installed or work on Raspberry Pi OS.
4. Provision an approved model pack yourself under `$KONJE_MODEL_ROOT/models/$KONJE_MODEL_PACK`, then set `KONJE_WORKER_PATH` to the **absolute path** of `tools/recognition_worker.py`.
5. With three adult consenting volunteers, evaluate face angles, distance, lighting, unknown bystanders, identical-looking faces, blurred images, multi-face images and errors. Tune all model/capture thresholds from data. Cosine similarities are not calibrated probabilities.
6. Measure capture, Python/model cold start, inference and speech latencies independently. If cold-start cost dominates, evaluate a persistent *local* inference process or a properly licensed ONNX C++ runtime on the Pi. No remote face forwarding is in this repo.

The versioned IPC is documented in `ARCHITECTURE.md`. `worker_protocol.py` validates up to 3 JPEGs and rejects malformed envelopes without touching disk. The current worker chooses the sharpest eligible frame and refuses zero/multiple faces. It emits `EMBEDDING ...` or `UNCERTAIN` only; errors are not distinguishable from uncertainty in the current protocol, and this needs improvement before assisted use.

Defaults (`0.60` cosine policy, `0.10` margin, image sharpness `20`, face detection `0.8`, enrollment consistency `0.75`) are *experimental placeholders*. They are not safety guarantees.