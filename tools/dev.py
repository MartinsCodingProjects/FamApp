"""`make dev`: start every process in dev/Procfile, prefix their output, stop all together.

Ctrl-C (or SIGTERM) stops everything; if one process exits, the others are stopped too and
its exit code is returned.

    python tools/dev.py [--procfile dev/Procfile]
"""

from __future__ import annotations

import argparse
import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def parse_procfile(path: Path) -> list[tuple[str, str]]:
    processes = []
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        name, sep, command = line.partition(":")
        if not sep or not name.strip() or not command.strip():
            raise ValueError(f"{path}:{number}: expected 'name: command'")
        processes.append((name.strip(), command.strip()))
    if not processes:
        raise ValueError(f"{path}: no processes")
    return processes


def _pump(name: str, width: int, stream, lock: threading.Lock) -> None:
    for line in iter(stream.readline, ""):
        with lock:
            sys.stdout.write(f"{name:<{width}} | {line}")
            sys.stdout.flush()


def run(processes: list[tuple[str, str]], cwd: Path) -> int:
    width = max(len(name) for name, _ in processes)
    lock = threading.Lock()
    children: list[tuple[str, subprocess.Popen]] = []
    finished = threading.Event()
    result = {"code": 0}

    def stop(*_args) -> None:
        finished.set()

    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    for name, command in processes:
        child = subprocess.Popen(
            ["bash", "-c", f"exec {command}"],
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            start_new_session=True,
        )
        children.append((name, child))
        threading.Thread(target=_pump, args=(name, width, child.stdout, lock), daemon=True).start()

        def watch(name=name, child=child) -> None:
            code = child.wait()
            if not finished.is_set():
                with lock:
                    print(f"{'dev':<{width}} | {name} exited with {code}, stopping all", flush=True)
                result["code"] = code or 1
                finished.set()

        threading.Thread(target=watch, daemon=True).start()

    finished.wait()
    for _name, child in children:
        if child.poll() is None:
            os.killpg(child.pid, signal.SIGTERM)
    for _name, child in children:
        try:
            child.wait(10)
        except subprocess.TimeoutExpired:
            os.killpg(child.pid, signal.SIGKILL)
    return result["code"]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="start the local dev processes")
    parser.add_argument("--procfile", type=Path, default=ROOT / "dev/Procfile")
    args = parser.parse_args(argv)
    return run(parse_procfile(args.procfile), ROOT)


if __name__ == "__main__":
    sys.exit(main())
