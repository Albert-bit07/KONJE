"""Dependency-free, fail-closed tests for the optional OpenCV worker."""
import io
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import opencv_worker


class WorkerTests(unittest.TestCase):
    def test_missing_models_do_not_download(self):
        with patch.dict(os.environ, {}, clear=True):
            self.assertIsNone(opencv_worker.model_paths())
            output = io.StringIO()
            self.assertEqual(opencv_worker.run(io.BytesIO(b"junk"), output), 0)
            self.assertEqual(output.getvalue(), "UNCERTAIN\n")

    def test_only_provisioned_onnx_models(self):
        with tempfile.TemporaryDirectory() as temp:
            a = Path(temp) / "a.onnx"
            b = Path(temp) / "b.onnx"
            a.write_bytes(b"placeholder")
            self.assertIsNone(opencv_worker.model_paths({"KONJE_YUNET_MODEL": str(a), "KONJE_SFACE_MODEL": str(b)}))
            b.write_bytes(b"placeholder")
            self.assertEqual(opencv_worker.model_paths({"KONJE_YUNET_MODEL": str(a), "KONJE_SFACE_MODEL": str(b)}), (a, b))

    def test_corrupt_envelope_is_uncertain(self):
        with patch.object(opencv_worker, "model_paths", return_value=("a.onnx", "b.onnx")):
            output = io.StringIO()
            opencv_worker.run(io.BytesIO(b"not a valid burst"), output)
            self.assertEqual(output.getvalue(), "UNCERTAIN\n")

    def test_embedding_format(self):
        with patch.object(opencv_worker, "model_paths", return_value=("a.onnx", "b.onnx")):
            with patch.object(opencv_worker, "extract", return_value=[0.6, 0.8]):
                output = io.StringIO()
                burst = b"KONJE1\x01\x06\x00\x00\x00\xff\xd8ab\xff\xd9"
                opencv_worker.run(io.BytesIO(burst), output)
                self.assertEqual(output.getvalue(), "EMBEDDING 0.6 0.8\n")

    def test_oversized_input_is_uncertain(self):
        with patch.object(opencv_worker, "model_paths", return_value=("a.onnx", "b.onnx")):
            output = io.StringIO()
            opencv_worker.run(io.BytesIO(b"x" * (opencv_worker.MAX_INPUT + 1)), output)
            self.assertEqual(output.getvalue(), "UNCERTAIN\n")


if __name__ == "__main__":
    unittest.main()