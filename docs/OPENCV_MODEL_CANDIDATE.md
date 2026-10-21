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
