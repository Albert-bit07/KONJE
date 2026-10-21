# OpenCV YuNet + SFace candidate (experimental)

This backend is an alternative to the existing InsightFace worker, not an evaluated winner.

## Why this candidate
The official OpenCV Zoo supports YuNet face detection with landmarks and SFace embedding extraction through OpenCV DNN. It can run on CPU and avoids a dependency on the InsightFace application framework. Official references:
- https://github.com/opencv/opencv_zoo/tree/main/models/face_detection_yunet
- https://github.com/opencv/opencv_zoo/tree/main/models/face_recognition_sface
- https://docs.opencv.org/doc/doxygen/html/d0/dd4/tutorial_dnn_face.html

**Model licensing and training-data provenance require review for intended deployment.** OpenCV Zoo model-directory licensing does not by itself establish suitability for every downstream commercial/medical use. No models or images are bundled.

## Provisioning

Install a version of OpenCV with `cv2.FaceDetectorYN` and `cv2.FaceRecognizerSF` and NumPy on the target device. Check those APIs are available before real testing. Place reviewed ONNX model files outside Git, and set absolute paths:

```bash
export KONJE_YUNET_MODEL=/home/konje/models/face_detection_yunet_2023mar.onnx
export KONJE_SFACE_MODEL=/home/konje/models/face_recognition_sface_2021dec.onnx
export KONJE_WORKER_PATH=/home/konje/KONJE/tools/opencv_worker.py
```

The C++ app uses KONJE_WORKER_PATH as a subprocess. This script consumes the existing versioned `KONJE1` JPEG burst from stdin, does not download or store frames, and emits only `EMBEDDING ...` or `UNCERTAIN`. It returns uncertain if model paths are absent, no/ambiguous faces, malformed images, or inference fails.

The current face-size (70 px), sharpness (20), and detection-score (0.9) checks are **unvalidated heuristics**. The C++ matching policy also has uncalibrated thresholds. No positive identity assertion should be trusted for real people until a consented validation set and false-match evaluation are complete.

## Verification

```bash
python3 -m unittest discover -s tools -p 'test_*.py' -v
python3 -m py_compile tools/opencv_worker.py
```

These tests verify protocol behavior and fail-closed paths **without** running real ONNX inference. Next evidence required: model checksum/provenance, ARM64 OpenCV API availability, CPU/RAM/latency benchmarks, accuracy/false-match assessment on consented images, and camera-to-speech test on Raspberry Pi 5.

Long-term: compare cold-start against a persistent worker with bounded requests, explicit deadlines and restart supervision. A model should not be selected based on published benchmark scores alone.

## Automated local preflight and initial timing

`tools/model_preflight.py` checks that both ONNX files are present, records their SHA-256 hashes, confirms OpenCV's face APIs and, when explicitly given a **consented local JPEG**, runs actual extraction several times and reports aggregate milliseconds. It stores no input images or embeddings. Because `opencv_worker.extract` initializes models on each call, these are **cold-start + inference** timings, not persistent-worker throughput. Do not interpret the generated embedding count as recognition accuracy.

```bash
# After provisioning reviewed model files and installing OpenCV/NumPy:
python3 tools/model_preflight.py
python3 tools/model_preflight.py --image /path/to/consented-local-sample.jpg --runs 5 --out /tmp/konje-model-report.json
python3 -m unittest discover -s tools -p 'test_*.py' -v
```

The report contains model digests, runtime API capability, and aggregate timings only. `--out` refuses to overwrite existing reports and uses owner-only permissions. Do not commit private samples, model weights, or reports containing device-specific paths. This preflight deliberately does **not** tune cosine thresholds: determining safe acceptance/margin cutoffs requires genuine positive/negative enrollment pairs, unknown faces, lighting variation, and consented ground truth. Device benchmarking and that evaluation are outstanding.
