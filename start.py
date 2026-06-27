#!/usr/bin/env python3
"""One-command launcher for littleman.

Usage:
    python start.py              # setup (if needed) + start API + scheduler
    python start.py --setup      # force dependency install/migrations/build
    python start.py --no-setup   # skip setup checks
    python start.py --dev        # start API (reload) + Vite dev UI
    python start.py --boot       # run First Light, then start API + scheduler

The script is intentionally self-contained: it works on Windows, macOS, and Linux,
with or without `uv` installed.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
DIST_DIR = FRONTEND_DIR / "dist"


def _has_uv() -> bool:
    return shutil.which("uv") is not None


def _prefix(prefix: str, stream) -> None:
    """Stream lines from a pipe with a colored prefix."""
    for raw in iter(stream.readline, b""):
        line = raw.decode("utf-8", errors="replace").rstrip()
        if line:
            print(f"[{prefix}] {line}")
    stream.close()


def _run(label: str, cmd: list[str], cwd: Path | None = None) -> None:
    """Run a command synchronously and stream its output."""
    print(f"\n==> {label}: {' '.join(cmd)}\n")
    proc = subprocess.Popen(
        cmd,
        cwd=cwd or PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    _prefix(label, proc.stdout)  # type: ignore[arg-type]
    proc.wait()
    if proc.returncode != 0:
        raise RuntimeError(f"{label} failed with exit code {proc.returncode}")


def _python_cmd(*parts: str) -> list[str]:
    if _has_uv():
        return ["uv", "run", *parts]
    venv_python = (
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
        if sys.platform == "win32"
        else PROJECT_ROOT / ".venv" / "bin" / "python"
    )
    if venv_python.exists():
        return [str(venv_python), *parts]
    return [sys.executable, *parts]


def setup(force: bool = False) -> None:
    """Install Python + Node deps, run migrations, build the frontend."""
    needs_setup = force or not (PROJECT_ROOT / ".venv").exists() or not (FRONTEND_DIR / "node_modules").exists()

    if needs_setup:
        if _has_uv():
            _run("install python deps", ["uv", "sync", "--all-extras"])
        else:
            _run("create venv", [sys.executable, "-m", "venv", ".venv"])
            _run("install python deps", _python_cmd("-m", "pip", "install", "-e", ".[dev,browser]"))

        _run("install node deps", ["npm", "install"], cwd=FRONTEND_DIR)

    _run("run migrations", _python_cmd("-m", "alembic", "upgrade", "head"))

    if needs_setup or not DIST_DIR.exists():
        _run("build frontend", ["npm", "run", "build"], cwd=FRONTEND_DIR)


def _start_service(label: str, cmd: list[str]) -> subprocess.Popen:
    print(f"\n==> Starting {label}: {' '.join(cmd)}\n")
    proc = subprocess.Popen(
        cmd,
        cwd=PROJECT_ROOT,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
    )
    t = threading.Thread(target=_prefix, args=(label, proc.stdout), daemon=True)
    t.start()
    return proc


def start(dev: bool = False) -> None:
    """Start the runtime services and wait for Ctrl+C."""
    api_cmd = _python_cmd("-m", "uvicorn", "littleman.api.app:app", "--host", "0.0.0.0", "--port", "8000")

    if dev:
        services = {
            "api": api_cmd + ["--reload"],
            "ui": ["npm", "run", "dev"],
        }
        print("\n[dev mode] API: http://localhost:8000 | Vite UI: http://localhost:5173")
    else:
        services = {
            "api": api_cmd,
            "scheduler": _python_cmd("-m", "littleman"),
        }
        print("\n[runtime] API + scheduler: http://localhost:8000")

    procs = {name: _start_service(name, cmd) for name, cmd in services.items()}

    try:
        for proc in procs.values():
            proc.wait()
    except KeyboardInterrupt:
        print("\n==> Shutting down...")
        for proc in procs.values():
            proc.terminate()
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        raise SystemExit(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="Start the littleman agent platform.")
    parser.add_argument("--setup", action="store_true", help="Force setup before starting.")
    parser.add_argument("--no-setup", action="store_true", help="Skip setup checks.")
    parser.add_argument("--dev", action="store_true", help="Run API reload + Vite dev UI.")
    parser.add_argument("--boot", action="store_true", help="Run First Light before starting.")
    args = parser.parse_args()

    if not args.no_setup:
        setup(force=args.setup)

    if args.boot:
        _run("First Light", _python_cmd("-m", "littleman", "boot"))

    start(dev=args.dev)


if __name__ == "__main__":
    main()
