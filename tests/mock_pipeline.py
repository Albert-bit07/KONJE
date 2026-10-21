"""Full command-flow smoke test with FAKE JPEG, FAKE embeddings and FAKE speech.

Does NOT establish camera, voice or face recognition performance.
"""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time


def main() -> int:
    executable = str(Path(sys.argv[1]).resolve())
    with tempfile.TemporaryDirectory(prefix="konje-mock-") as tmp:
        root = Path(tmp)
        bin_dir = root / "bin"
        bin_dir.mkdir()
        camera = bin_dir / "rpicam-still"
        camera.write_text(
            "#!/bin/sh\n"
            "printf '\\377\\330FAKE_FRAME\\377\\331'\n",
            encoding="utf-8",
        )
        worker = root / "fake_worker.py"
        worker.write_text(
            "import sys\n"
            "data=sys.stdin.buffer.read(13*1024*1024)\n"
            "if not data.startswith(b'KONJE1') or data[6] not in (1,2,3):\n"
            " print('UNCERTAIN')\n"
            "else:\n"
            " count=data[6]; pos=7; valid=True\n"
            " for i in range(count):\n"
            "  if len(data)<pos+4: valid=False; break\n"
            "  size=int.from_bytes(data[pos:pos+4],'little'); pos+=4\n"
            "  frame=data[pos:pos+size]; pos+=size\n"
            "  valid &= size>4 and frame.startswith(bytes.fromhex('ffd8')) and frame.endswith(bytes.fromhex('ffd9'))\n"
            " print('EMBEDDING 1 0 0' if valid and pos==len(data) else 'UNCERTAIN')\n",
            encoding="utf-8",
        )
        speech = bin_dir / "espeak-ng"
        speech.write_text(
            "#!/usr/bin/env python3\n"
            "import os,pathlib,sys\n"
            "pathlib.Path(os.environ['KONJE_MOCK_SPEECH_LOG']).write_bytes(sys.stdin.buffer.read())\n",
            encoding="utf-8",
        )
        camera.chmod(0o755)
        speech.chmod(0o755)
        speech_log = root / "speech.txt"
        env = os.environ.copy()
        env.update({
            "HOME": str(root),
            "KONJE_WORKER_PATH": str(worker),
            "KONJE_CAMERA": "rpicam",
            "KONJE_SPEECH": "on",
            "KONJE_MOCK_SPEECH_LOG": str(speech_log),
            "PATH": f"{bin_dir}{os.pathsep}{env['PATH']}",
        })

        def invoke(*args: str, input_text: str = "") -> str:
            p = subprocess.run([executable, *args], env=env, input=input_text,
                               capture_output=True, text=True, timeout=40)
            assert p.returncode == 0, (args, p.returncode, p.stdout, p.stderr)
            return p.stdout

        invoke("init-key")
        prompt = "CONSENT CONFIRMED\nMock Person\nfriend\nThis is Mock Person, your friend.\n\n\n\n"
        assert "Stored encrypted profile" in invoke("enroll", "volunteerA", input_text=prompt)
        assert "volunteerA" in invoke("list")

        p = subprocess.Popen([executable, "run"], env=env, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert p.stdin is not None
        p.stdin.write("\n")
        p.stdin.flush()
        # Wait for the terminal outcome before issuing q; q cancels an active request.
        import select
        observed = ""
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            ready, _, _ = select.select([p.stdout], [], [], 0.2)
            if ready:
                observed += p.stdout.readline()
                if "recognized" in observed or "uncertain" in observed or "unavailable" in observed:
                    break
        stdout, stderr = p.communicate("q\n", timeout=10)
        stdout = observed + stdout
        assert p.returncode == 0, (stdout, stderr)
        assert "recognized (approved introduction spoken)" in stdout, (stdout, stderr)
        assert speech_log.read_text() == "This is Mock Person, your friend."
        print("SIMULATED request -> memory capture -> worker -> encrypted match -> approved speech: PASS")

        invoke("revoke", "volunteerA")
        assert invoke("list") == ""
        speech_log.unlink()
        p = subprocess.Popen([executable, "run"], env=env, stdin=subprocess.PIPE,
                             stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        assert p.stdin
        p.stdin.write("\n")
        p.stdin.flush()
        import select
        observed = ""
        deadline = time.monotonic() + 25
        while time.monotonic() < deadline:
            ready, _, _ = select.select([p.stdout], [], [], 0.2)
            if ready:
                observed += p.stdout.readline()
                if "uncertain" in observed:
                    break
        stdout, stderr = p.communicate("q\n", timeout=10)
        stdout = observed + stdout
        assert "uncertain" in stdout and not speech_log.exists(), (stdout, stderr)
        print("SIMULATED revocation -> no identity or speech: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())