"""Simulated mid-speech profile revocation must terminate TTS promptly.

Uses fake camera bytes, fake model embeddings and a fake TTS process.
No real faces, models, speaker or volunteers are involved.
"""
import os
from pathlib import Path
import select
import subprocess
import sys
import tempfile
import time


def invoke(executable, env, *args, input_text=""):
    done = subprocess.run([executable, *args], env=env, input=input_text,
                          text=True, capture_output=True, timeout=30)
    if done.returncode:
        raise AssertionError((args, done.returncode, done.stderr))
    return done.stdout


def wait_for_file(path, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.exists():
            return
        time.sleep(.025)
    raise AssertionError("TTS worker did not start")


def main():
    app = str(Path(sys.argv[1]).resolve())
    with tempfile.TemporaryDirectory(prefix="konje-revoke-") as tmp:
        root = Path(tmp)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        camera = bin_dir / "rpicam-still"
        camera.write_text("#!/bin/sh\nprintf '\\377\\330FAKE_FRAME\\377\\331'\n")
        camera.chmod(0o700)
        fake_model = root / "model.py"
        fake_model.write_text("print('EMBEDDING 1 0 0')\n")
        speech = bin_dir / "espeak-ng"
        speech.write_text(
            "#!/usr/bin/env python3\n"
            "import os, pathlib, sys, time\n"
            "sys.stdin.buffer.read()\n"
            "pathlib.Path(os.environ['KONJE_TEST_SPEECH_START']).write_text('started')\n"
            "time.sleep(6)\n"
            "pathlib.Path(os.environ['KONJE_TEST_SPEECH_FINISH']).write_text('finished')\n"
        )
        speech.chmod(0o700)
        started = root / "speech-started"
        finished = root / "speech-finished"
        env = os.environ.copy()
        env.update({
            "HOME": str(root),
            "KONJE_WORKER_PATH": str(fake_model),
            "KONJE_CAMERA": "rpicam",
            "KONJE_MODEL_ID": "mock-model-v1",
            "KONJE_SPEECH": "on",
            "KONJE_TEST_SPEECH_START": str(started),
            "KONJE_TEST_SPEECH_FINISH": str(finished),
            "PATH": str(bin_dir) + os.pathsep + env["PATH"],
        })
        invoke(app, env, "init-key")
        prompt = "CONSENT CONFIRMED\nVolunteer\nfriend\nApproved test phrase\n\n\n\n"
        assert "Stored encrypted profile" in invoke(app, env, "enroll", "v1", input_text=prompt)

        runner = subprocess.Popen([app, "run"], env=env, stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            runner.stdin.write(b"\n")
            runner.stdin.flush()
            wait_for_file(started, 20)
            invoke(app, env, "revoke", "v1")
            deadline = time.monotonic() + 8
            seen = b""
            while time.monotonic() < deadline:
                r, _, _ = select.select([runner.stdout.fileno()], [], [], .1)
                if r:
                    chunk = os.read(runner.stdout.fileno(), 4096)
                    if not chunk:
                        break
                    seen += chunk
                    if b"profile revoked or changed during speech" in seen:
                        break
            assert b"profile revoked or changed during speech" in seen, seen
            assert not finished.exists(), "Cancelled TTS continued to completion"
            runner.stdin.write(b"q\n")
            runner.stdin.flush()
            runner.communicate(timeout=10)
            assert runner.returncode == 0
            print("PASS: local profile revocation interrupted active fake speech")
        finally:
            if runner.poll() is None:
                runner.kill()
                runner.communicate(timeout=5)


if __name__ == "__main__":
    main()