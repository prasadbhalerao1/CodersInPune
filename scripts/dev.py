"""Run Relay locally in one terminal: `python scripts/dev.py`.

Starts PostgreSQL (if it isn't running), the API (which also runs the background jobs
when RELAY_EMBEDDED_WORKER=true, as `scripts/setup.py` configures) and the web app, with
their output prefixed. Ctrl+C stops everything. Standard library only.
"""

import os
import signal
import subprocess
import sys
import threading
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
WINDOWS = sys.platform == "win32"
PROCESSES = [
    ("api", ROOT / "backend", ["uv", "run", "relay-api"]),
    ("web", ROOT / "frontend", ["pnpm", "dev"]),
]


def pipe(name: str, proc: subprocess.Popen[bytes]) -> None:
    assert proc.stdout is not None
    for raw in proc.stdout:
        line = raw.decode(errors="replace").rstrip()
        print(f"[{name}] {line}", flush=True)


def main() -> None:
    if not (ROOT / "backend" / ".env").exists():
        print("Run `python scripts/setup.py` first.")
        sys.exit(1)
    subprocess.run(["docker", "compose", "up", "-d", "--wait"], cwd=ROOT, check=True, shell=WINDOWS)
    procs = []
    for name, cwd, cmd in PROCESSES:
        proc = subprocess.Popen(
            cmd,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=WINDOWS,
            env={**os.environ, "FORCE_COLOR": "1"},
        )
        procs.append(proc)
        threading.Thread(target=pipe, args=(name, proc), daemon=True).start()
    print("\nRelay is starting: open http://localhost:3000 (Ctrl+C to stop)\n", flush=True)
    try:
        while all(p.poll() is None for p in procs):
            threading.Event().wait(0.5)
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs:
            if p.poll() is None:
                if WINDOWS:
                    subprocess.run(["taskkill", "/T", "/F", "/PID", str(p.pid)], capture_output=True)
                else:
                    p.send_signal(signal.SIGINT)
        for p in procs:
            try:
                p.wait(timeout=10)
            except subprocess.TimeoutExpired:
                p.kill()


if __name__ == "__main__":
    # Windows consoles and redirected output default to a legacy code page; tool output
    # (e.g. Next.js) uses Unicode symbols.
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    main()
