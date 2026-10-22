"""Dependency-free tests for KONJE's model readiness reporting."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
import model_preflight


class ModelPreflightTests(unittest.TestCase):
    def test_unconfigured_or_invalid_model(self):
        self.assertEqual(model_preflight.inspect_model(None)["reason"], "not_configured")
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "missing.onnx"
            self.assertFalse(model_preflight.inspect_model(str(path))["ready"])
            path.write_bytes(b"tiny")
            self.assertEqual(model_preflight.inspect_model(str(path))["reason"], "implausibly_small")

    def test_model_hash_is_deterministic(self):
        import hashlib
        with tempfile.TemporaryDirectory() as folder:
            data = b"ONNX-CANDIDATE-TEST" * 128
            path = Path(folder) / "candidate.onnx"
            path.write_bytes(data)
            result = model_preflight.inspect_model(str(path))
            self.assertTrue(result["ready"])
            self.assertEqual(result["bytes"], len(data))
            self.assertEqual(result["sha256"], hashlib.sha256(data).hexdigest())

    def test_percentile_small_samples(self):
        self.assertEqual(model_preflight.percentile([3], 0.95), 3)
        self.assertEqual(model_preflight.percentile([9, 1, 5, 7, 3], 0.5), 5)
        self.assertEqual(model_preflight.percentile([9, 1, 5, 7, 3], 0.95), 9)

    def test_missing_models_report_without_paths_or_samples(self):
        report = model_preflight.probe(None, None)
        self.assertEqual(report["model"], "opencv-yunet-sface")
        self.assertFalse(report["models"]["detector"]["ready"])
        self.assertFalse(report["models"]["recognizer"]["ready"])
        self.assertNotIn("embedding", json.dumps(report).lower())

    def test_cli_rejects_invalid_runs(self):
        result = subprocess.run(
            [sys.executable, str(Path(model_preflight.__file__)), "--runs", "0"],
            capture_output=True, text=True, timeout=10,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--runs must be between 1 and 30", result.stderr)


if __name__ == "__main__":
    unittest.main()
