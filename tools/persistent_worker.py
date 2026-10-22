#!/usr/bin/env python3
"""Single-model, bounded, local UNIX-socket inference service.

Wire protocol (little-endian): request length:u32, model-id length:u16,
model-id UTF-8, KONJE1 burst. Response length:u32, ASCII worker response.
A failed/unavailable inference returns UNCERTAIN; no biometric data is logged.
"""
import argparse
import os
from pathlib import Path
import signal
import socket
import stat
import struct
import sys

from opencv_worker import MAX_INPUT, format_result, load_models, extract_loaded
from worker_protocol import read_burst
from model_identity import verified_paths

MAX_REQUEST = MAX_INPUT + 2 + 128
MAX_RESPONSE = 65536


def recv_exact(sock, count):
    parts = bytearray()
    while len(parts) < count:
        item = sock.recv(count - len(parts))
        if not item:
            raise ValueError("short request")
        parts.extend(item)
    return bytes(parts)


def handle(sock, expected_id, embed):
    """One connection; no queue, no user-provided names, deadlines on I/O."""
    answer = b"UNCERTAIN\n"
    try:
        (length,) = struct.unpack("<I", recv_exact(sock, 4))
        if not 9 <= length <= MAX_REQUEST:
            raise ValueError("invalid request length")
        payload = recv_exact(sock, length)
        (identity_length,) = struct.unpack("<H", payload[:2])
        if not 1 <= identity_length <= 128 or length <= 2 + identity_length:
            raise ValueError("invalid model identity")
        identity = payload[2:2 + identity_length].decode("ascii")
        if identity != expected_id:
            raise ValueError("model mismatch")
        frames = read_burst(payload[2 + identity_length:])
        answer = format_result(embed(frames))
        if len(answer) > MAX_RESPONSE:
            raise ValueError("oversized inference output")
    except (OSError, ValueError, UnicodeError, OverflowError):
        pass
    except Exception:
        # Model/runtime failures never authorize an identity announcement.
        pass
    sock.sendall(struct.pack("<I", len(answer)) + answer)


def serve(socket_path, model_id, embed, *, on_ready=None, stop=None):
    """Fixed-size accept backlog; serialized inference; owner-only socket."""
    path = Path(socket_path)
    if not path.is_absolute() or len(os.fsencode(path)) >= 104:
        raise ValueError("socket requires short absolute path")
    parent = path.parent
    st = parent.lstat()
    if not stat.S_ISDIR(st.st_mode) or st.st_uid != os.getuid() or st.st_mode & 0o077:
        raise ValueError("socket parent must be private and owned by current user")
    if path.exists() or path.is_symlink():
        raise FileExistsError("socket already exists; never replace arbitrary files")
    old_umask = os.umask(0o077)
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as listener:
            listener.bind(str(path))
            created_inode = path.lstat().st_ino
            os.chmod(path, 0o600)
            listener.listen(2)
            listener.settimeout(0.25)
            if on_ready is not None:
                on_ready()
            try:
                while stop is None or not stop():
                    try:
                        conn, _ = listener.accept()
                    except socket.timeout:
                        continue
                    with conn:
                        conn.settimeout(5)
                        try:
                            handle(conn, model_id, embed)
                        except (OSError, ValueError):
                            pass
            finally:
                # Unlink only the socket inode we created; refuse to delete replacements.
                try:
                    if path.is_socket() and path.lstat().st_ino == created_inode:
                        path.unlink()
                except OSError:
                    pass
    finally:
        os.umask(old_umask)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--socket", required=True, help="private local UNIX socket path")
    args = parser.parse_args(argv)
    paths = verified_paths()
    model_id = os.environ.get("KONJE_MODEL_ID", "")
    if paths is None or not model_id:
        print("Model not provisioned or identity mismatch", file=sys.stderr)
        return 2
    try:
        runtime = load_models(*paths)  # Exactly once per daemon startup.
    except Exception:
        print("Model initialization failed", file=sys.stderr)
        return 2
    exiting = False
    def exit_handler(signum, frame):
        nonlocal exiting
        exiting = True
    signal.signal(signal.SIGTERM, exit_handler)
    signal.signal(signal.SIGINT, exit_handler)
    try:
        serve(args.socket, model_id, lambda frames: extract_loaded(frames, runtime), stop=lambda: exiting)
    except (OSError, ValueError):
        print("Persistent worker startup failed", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())