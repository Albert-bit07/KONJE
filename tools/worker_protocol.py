"""Small, versioned binary frame-burst decoder for local in-memory IPC.

No disk writes or third-party dependencies.
"""
MAGIC = b"KONJE1"
MAX_JPEG = 4 * 1024 * 1024


def read_burst(raw: bytes) -> list[bytes]:
    if len(raw) < 7 or raw[:6] != MAGIC or raw[6] not in (1, 2, 3):
        raise ValueError("unsupported frame envelope")
    frames = []
    pos = 7
    for _ in range(raw[6]):
        if len(raw) - pos < 4:
            raise ValueError("truncated frame length")
        size = int.from_bytes(raw[pos:pos + 4], "little")
        pos += 4
        if not 4 <= size <= MAX_JPEG or len(raw) - pos < size:
            raise ValueError("invalid frame size")
        frame = raw[pos:pos + size]
        pos += size
        if not frame.startswith(b"\xff\xd8") or not frame.endswith(b"\xff\xd9"):
            raise ValueError("invalid JPEG markers")
        frames.append(frame)
    if pos != len(raw):
        raise ValueError("trailing bytes")
    return frames