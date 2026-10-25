"""Download the two face models (about 40 MB) and check they are the exact right files.
Same files and checksums as Albert's KONJE repo (tools/provision_models.py)."""
import hashlib
import urllib.request
from pathlib import Path

BASE = "https://huggingface.co/opencv/opencv_zoo/resolve/main/models/"
MODELS = {
    "face_detection_yunet_2023mar.onnx": (
        BASE + "face_detection_yunet/face_detection_yunet_2023mar.onnx",
        "8f2383e4dd3cfbb4553ea8718107fc0423210dc964f9f4280604804ed2552fa4"),
    "face_recognition_sface_2021dec.onnx": (
        BASE + "face_recognition_sface/face_recognition_sface_2021dec.onnx",
        "0ba9fbfa01b5270c96627c4ef784da859931e02f04419c829e83484087c34e79"),
}

folder = Path(__file__).resolve().parent / "models"
folder.mkdir(exist_ok=True)
for name, (url, expected) in MODELS.items():
    path = folder / name
    if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == expected:
        print("ok      ", name)
        continue
    print("download", name)
    data = urllib.request.urlopen(url, timeout=60).read()
    if hashlib.sha256(data).hexdigest() != expected:
        raise SystemExit(f"Checksum mismatch for {name}; not saving it.")
    path.write_bytes(data)
print("Models ready.")
