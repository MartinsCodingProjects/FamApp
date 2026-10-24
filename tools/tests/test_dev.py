"""`make dev` smoke test (BUILDPLAN 1.3.10): the process runner starts the fakes; fake FCM accepts calls."""

import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request

from conftest import REPO

import dev


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def wait_for(url: str, timeout: float = 20) -> None:
    deadline = time.monotonic() + timeout
    while True:
        try:
            with urllib.request.urlopen(url, timeout=1):
                return
        except OSError:
            if time.monotonic() > deadline:
                raise
            time.sleep(0.1)


def test_make_dev_starts_fake_fcm():
    port = free_port()
    proc = subprocess.Popen(
        [sys.executable, str(REPO / "tools/dev.py")],
        cwd=REPO,
        env={**os.environ, "FAKE_FCM_PORT": str(port)},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        base = f"http://127.0.0.1:{port}"
        wait_for(f"{base}/fake/health")
        body = json.dumps({"message": {"token": "t", "data": {"t": "sync"}}}).encode()
        request = urllib.request.Request(f"{base}/v1/projects/p/messages:send", data=body, method="POST")
        with urllib.request.urlopen(request, timeout=5) as response:
            assert response.status == 200
        with urllib.request.urlopen(f"{base}/fake/messages", timeout=5) as response:
            assert len(json.loads(response.read())["messages"]) == 1
    finally:
        proc.send_signal(signal.SIGINT)
        output, _ = proc.communicate(timeout=20)
    assert proc.returncode == 0, output
    assert "fake-fcm | fake-fcm: listening" in output


def test_runner_stops_all_when_one_exits(tmp_path):
    procfile = tmp_path / "Procfile"
    procfile.write_text("sleeper: sleep 30\nfailing: exit 3\n", encoding="utf-8")
    started = time.monotonic()
    result = subprocess.run(
        [sys.executable, str(REPO / "tools/dev.py"), "--procfile", str(procfile)],
        capture_output=True,
        text=True,
        timeout=20,
    )
    assert result.returncode == 3
    assert "failing exited with 3" in result.stdout
    assert time.monotonic() - started < 15


def test_procfile_parsing(tmp_path):
    procfile = tmp_path / "Procfile"
    procfile.write_text("# comment\n\napi: uv run x --port 8000\n", encoding="utf-8")
    assert dev.parse_procfile(procfile) == [("api", "uv run x --port 8000")]
    procfile.write_text("broken line\n", encoding="utf-8")
    try:
        dev.parse_procfile(procfile)
    except ValueError as exc:
        assert "name: command" in str(exc)
    else:
        raise AssertionError("expected ValueError")
