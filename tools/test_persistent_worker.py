"""Dependency-free persistent worker input bounds and failure behavior."""
import socket
import struct
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from persistent_worker import handle


def envelope(identity, burst):
    body = struct.pack("<H", len(identity)) + identity + burst
    return struct.pack("<I", len(body)) + body


class PersistentWorkerTests(unittest.TestCase):
    def exercise(self, request):
        client, server = socket.socketpair()
        called = []
        try:
            client.sendall(request)
            client.shutdown(socket.SHUT_WR)
            handle(server, "verified-id", lambda frames: called.append(frames) or [1.0, 0.0])
            size = struct.unpack("<I", client.recv(4))[0]
            result = bytearray()
            while len(result) < size:
                result.extend(client.recv(size - len(result)))
            return bytes(result), called
        finally:
            client.close()
            server.close()

    def test_valid_burst_and_wrong_id(self):
        frame = b"\xff\xd8hello\xff\xd9"
        burst = b"KONJE1\x01" + struct.pack("<I", len(frame)) + frame
        response, called = self.exercise(envelope(b"verified-id", burst))
        self.assertEqual(response, b"EMBEDDING 1 0\n")
        self.assertEqual(called, [[frame]])
        response, called = self.exercise(envelope(b"other", burst))
        self.assertEqual(response, b"UNCERTAIN\n")
        self.assertFalse(called)

    def test_corrupt_or_huge_messages(self):
        for bad in (struct.pack("<I", 0), struct.pack("<I", 0xffffffff),
                    envelope(b"verified-id", b"wrong"),
                    envelope(b"verified-id", b"KONJE1\x01"),
                    envelope(b"", b"KONJE1\x01")):
            with self.subTest(bad=bad[:20]):
                result, called = self.exercise(bad)
                self.assertEqual(result, b"UNCERTAIN\n")
                self.assertFalse(called)


if __name__ == "__main__":
    unittest.main()