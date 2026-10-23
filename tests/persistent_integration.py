"""Exercise native C++ client and Python service, no model or private images."""
import os
import socket
import struct
import time
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "tools"))
from persistent_worker import serve


class NativePersistentTests(unittest.TestCase):
    def test_native_client_roundtrips_and_version_mismatch(self):
        with tempfile.TemporaryDirectory() as root:
            path = str(Path(root) / "model.sock")
            ready = threading.Event()
            stop = threading.Event()
            seen = []
            def embed(frames):
                seen.append(len(frames))
                return [0.6, 0.8]
            daemon = threading.Thread(
                target=serve,
                args=(path, "test-model-001", embed),
                kwargs={"on_ready": ready.set, "stop": stop.is_set}, daemon=True)
            daemon.start()
            self.assertTrue(ready.wait(3))
            try:
                for _ in range(3):
                    result = subprocess.run([sys.argv[1], path, "test-model-001"],
                                            capture_output=True, text=True, timeout=6, check=True)
                    self.assertEqual(result.stdout, "EMBEDDING 0.6 0.8\n")
                self.assertEqual(seen, [1, 1, 1])
                denied = subprocess.run([sys.argv[1], path, "different-model"],
                                        capture_output=True, text=True, timeout=6, check=True)
                self.assertEqual(denied.stdout, "UNCERTAIN\n")
                self.assertEqual(seen, [1, 1, 1])
                self.assertTrue(Path(path).stat().st_mode & 0o600)
            finally:
                stop.set()
                daemon.join(timeout=3)
            self.assertFalse(daemon.is_alive())
            self.assertFalse(Path(path).exists())

    def test_bad_request_and_worker_recovery(self):
        # Malformed inputs must fail closed without killing the long-running worker.
        with tempfile.TemporaryDirectory() as root:
            path = str(Path(root) / "model.sock")
            ready, stop = threading.Event(), threading.Event()
            calls = []
            def embed(frames):
                calls.append(len(frames))
                return [0.6, 0.8]
            daemon = threading.Thread(
                target=serve, args=(path, "test-model-001", embed),
                kwargs={"on_ready": ready.set, "stop": stop.is_set}, daemon=True)
            daemon.start()
            self.assertTrue(ready.wait(3))
            try:
                malformed = [
                    struct.pack("<I", 0),
                    struct.pack("<I", 999999999),
                    struct.pack("<I", 11) + struct.pack("<H", 1) + b"x" + b"badbytes",
                ]
                for request in malformed:
                    with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                        client.settimeout(3)
                        client.connect(path)
                        client.sendall(request)
                        size = struct.unpack("<I", self._read_exact(client, 4))[0]
                        self.assertLessEqual(size, 65536)
                        self.assertEqual(self._read_exact(client, size), b"UNCERTAIN\n")
                self.assertEqual(calls, [])
                healthy = subprocess.run([sys.argv[1], path, "test-model-001"],
                                         capture_output=True, text=True, timeout=6, check=True)
                self.assertEqual(healthy.stdout, "EMBEDDING 0.6 0.8\n")
                self.assertEqual(calls, [1])
            finally:
                stop.set()
                daemon.join(timeout=3)
            self.assertFalse(daemon.is_alive())

    @staticmethod
    def _read_exact(client, length):
        data = b""
        while len(data) < length:
            part = client.recv(length - len(data))
            if not part:
                raise AssertionError("worker disconnected before complete response")
            data += part
        return data

    def test_socket_unavailable_fails_closed(self):
        with tempfile.TemporaryDirectory() as root:
            missing = Path(root) / "missing.sock"
            result = subprocess.run([sys.argv[1], str(missing), "test-model-001"],
                                    capture_output=True, text=True, timeout=6, check=True)
            self.assertEqual(result.stdout, "UNAVAILABLE\n")


if __name__ == "__main__":
    unittest.main(argv=sys.argv[:1])