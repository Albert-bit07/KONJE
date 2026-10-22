"""Exercise model preflight outcomes without downloading models or using face images."""
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import model_preflight
import opencv_worker


class InferenceOutcomeTests(unittest.TestCase):
    def run_probe(self, outcomes):
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp) / "sample.jpg"
            image.write_bytes(b"\xff\xd8sample\xff\xd9")
            fake_cv2 = types.ModuleType("cv2")
            fake_cv2.__version__ = "test-runtime"
            fake_cv2.FaceDetectorYN = object()
            fake_cv2.FaceRecognizerSF = object()
            fake_cv2.error = RuntimeError
            fake_np = types.ModuleType("numpy")
            with patch.dict(sys.modules, {"cv2": fake_cv2, "numpy": fake_np}), \
                 patch.object(model_preflight, "inspect_model", return_value={"ready": True}), \
                 patch.object(opencv_worker, "extract", side_effect=outcomes):
                return model_preflight.probe("detector.onnx", "recognizer.onnx",
                                             image=str(image), iterations=len(outcomes))

    def test_no_embedding_is_not_success(self):
        result = self.run_probe([None, None, None])
        self.assertEqual(result["benchmark"]["status"], "inference_no_embedding")
        self.assertEqual(result["benchmark"]["embeddings_generated"], 0)

    def test_partial_inference_is_not_success(self):
        result = self.run_probe([[1.0], None, [1.0]])
        self.assertEqual(result["benchmark"]["status"], "incomplete_inference")
        self.assertEqual(result["benchmark"]["embeddings_generated"], 2)

    def test_all_valid_inference_is_success(self):
        result = self.run_probe([[1.0], [1.0], [1.0]])
        self.assertEqual(result["benchmark"]["status"], "complete")
        self.assertEqual(result["benchmark"]["runs"], 3)


if __name__ == "__main__":
    unittest.main()
