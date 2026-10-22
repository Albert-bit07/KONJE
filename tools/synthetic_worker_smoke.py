#!/usr/bin/env python3
"""Exercise the real OpenCV recognition worker using synthetic blank JPEG frames.

Requires installed SHA-256-pinned models. Does not use or persist human images.
"""
import io
import sys


def main():
    import cv2
    import numpy as np
    from opencv_worker import run

    frames = []
    for _ in range(3):
        success, jpeg = cv2.imencode(".jpg", np.zeros((480, 640, 3), dtype=np.uint8))
        if not success:
            raise RuntimeError("Cannot create synthetic JPEG")
        encoded = jpeg.tobytes()
        frames.append(encoded)

    request = b"KONJE1" + bytes((len(frames),))
    request += b"".join(len(frame).to_bytes(4, "little") + frame for frame in frames)
    output = io.StringIO()
    result = run(io.BytesIO(request), output)
    if result != 0 or output.getvalue() != "UNCERTAIN\n":
        raise RuntimeError("Blank JPEG burst must never identify a person")
    print("PASS: 3 blank JPEGs -> verified local OpenCV worker -> UNCERTAIN")


if __name__ == "__main__":
    sys.exit(main())
