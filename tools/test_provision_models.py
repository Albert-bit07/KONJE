"""Offline tests: model provisioning never depends on the network in CI."""
import hashlib
import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent))
import provision_models as pm


class ModelsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.detector = b"detector-provenance" * 200
        self.recognizer = b"recognizer-provenance" * 250
        self.models = (
            pm.Model("detector.onnx", "https://example.org/a", hashlib.sha256(self.detector).hexdigest(), 20000),
            pm.Model("recognizer.onnx", "https://example.org/b", hashlib.sha256(self.recognizer).hexdigest(), 20000),
        )
        self.patcher = patch.object(pm, "SPECS", self.models)
        self.patcher.start()
        self.addCleanup(self.patcher.stop)

    def test_missing_files_do_not_download(self):
        with self.assertRaisesRegex(ValueError, "Model unavailable"):
            pm.provision(self.root, download=False)
        self.assertFalse(list(self.root.iterdir()))

    def test_verifies_preinstalled_exact_bytes(self):
        (self.root / "detector.onnx").write_bytes(self.detector)
        (self.root / "recognizer.onnx").write_bytes(self.recognizer)
        result = pm.provision(self.root, download=False)
        self.assertIn("KONJE_MODEL_ID", result)
        self.assertIn(self.models[0].sha256, result)
        self.assertTrue(all((self.root / s.filename).is_file() for s in self.models))

    def test_download_atomic_and_reject_mismatched_bytes(self):
        content = io.BytesIO(b"tampered")
        with self.assertRaisesRegex(ValueError, "Checksum mismatch"):
            pm.fetch_verified(self.models[0], self.root, opener=lambda *a, **k: content)
        self.assertFalse((self.root / "detector.onnx").exists())
        self.assertFalse(list(self.root.glob(".download-*")))
        path = pm.fetch_verified(self.models[0], self.root, opener=lambda *a, **k: io.BytesIO(self.detector))
        self.assertEqual(path.read_bytes(), self.detector)
        self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_corrupt_existing_file_cannot_be_overwritten(self):
        path = self.root / "detector.onnx"
        path.write_bytes(b"wrong")
        with self.assertRaisesRegex(ValueError, "overwrite"):
            pm.fetch_verified(self.models[0], self.root)
        self.assertEqual(path.read_bytes(), b"wrong")

    def test_symlink_is_not_accepted(self):
        elsewhere = self.root / "outside"
        elsewhere.write_bytes(self.detector)
        symlink = self.root / "detector.onnx"
        symlink.symlink_to(elsewhere)
        self.assertFalse(pm.validate(symlink, self.models[0]))


if __name__ == "__main__":
    unittest.main()