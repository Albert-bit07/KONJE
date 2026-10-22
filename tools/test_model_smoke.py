import sys
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import model_smoke


class SmokeTests(unittest.TestCase):
    def test_missing_models_never_execute(self):
        with patch.object(model_smoke, "verified_paths", return_value=None):
            self.assertEqual(model_smoke.main(), 2)

    def test_fake_api_success_without_real_face(self):
        cv = MagicMock()
        cv.__version__ = "test"
        detector = cv.FaceDetectorYN.create.return_value
        detector.detect.return_value = (0, None)
        np = MagicMock()
        np.uint8 = object()
        np.float32 = object()
        array = MagicMock()
        array.size = 128
        np.asarray.return_value.reshape.return_value = array
        np.isfinite.return_value.all.return_value = True
        result = model_smoke.smoke((Path("a.onnx"), Path("b.onnx")), cv, np)
        self.assertEqual(result["result"], "loaded_and_executed")
        self.assertFalse(result["recognition_accuracy_evaluated"])
        self.assertEqual(result["embedding_dimensions"], 128)
        detector.detect.assert_called_once()

    def test_bad_embedding_shape_fails(self):
        cv = MagicMock()
        cv.FaceDetectorYN.create.return_value.detect.return_value = (0, None)
        np = MagicMock()
        array = MagicMock()
        array.size = 0
        np.asarray.return_value.reshape.return_value = array
        with self.assertRaises(RuntimeError):
            model_smoke.smoke((Path("a.onnx"), Path("b.onnx")), cv, np)

if __name__ == "__main__":
    unittest.main()