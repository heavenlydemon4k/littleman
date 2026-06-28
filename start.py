#!/usr/bin/env python3
"""One-command launcher for littleman.

Usage:
    python start.py              # setup (if needed) + start API + scheduler
    python start.py --setup      # force dependency install/build
    python start.py --no-setup   # skip setup checks
    python start.py --fresh      # wipe state and start from scratch (for testing)
    python start.py --dev        # start API (reload) + Vite dev UI
    python start.py --boot       # run First Light, then start API + scheduler

The script is intentionally self-contained: it works on Windows, macOS, and Linux,
with or without `uv` installed.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = PROJECT_ROOT / "frontend"
DIST_DIR = FRONTEND_DIR / "dist"
WORKSPACE_DIR = PROJECT_ROOT / "workspace"
CONSTRUCT_DIR = WORKSPACE_DIR / "construct"

# Documents that, if present, signal First Light has already run.
FIRST_LIGHT_DOCS = (
    "PRIORITIES.md",
    "MACRO_PLAN.md",
    "SELF.md",
    "DIRECTIVE.md",
    "REFLECTION.md",
    "EXPOSURE.md",
    "CALENDAR.md",
    "HYPOTHESES.md",
    "BLOCKERS.md",
    "SKILL_NOTES.md",
    "TURNS.md",
)


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


def _venv_exists() -> bool:
    return (
        PROJECT_ROOT / ".venv" / "Scripts" / "python.exe"
        if sys.platform == "win32"
        else PROJECT_ROOT / ".venv" / "bin" / "python"
    ).exists()


def fresh_clean() -> None:
    """Remove all runtime state so the next launch starts from a blank slate.

    This is intentionally destructive: it wipes the database, the built frontend,
    the agent's self-authored construct docs, and the compiled SOUL.md. Templates,
    skill docs, AGENTS.md, and project code are left untouched.
    """
    print("\n==> Fresh start: wiping runtime state\n")

    db_file = PROJECT_ROOT / "littleman.db"
    if db_file.exists():
        db_file.unlink()
        print(f"removed {db_file}")

    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
        print(f"removed {DIST_DIR}")

    soul = WORKSPACE_DIR / "SOUL.md"
    if soul.exists():
        soul.unlink()
        print(f"removed {soul}")

    if CONSTRUCT_DIR.exists():
        for name in FIRST_LIGHT_DOCS:
            path = CONSTRUCT_DIR / name
            if path.exists():
                path.unlink()
                print(f"removed {path}")

    # Clean python cache so stale bytecode doesn't shadow freshly edited code.
    for pycache in PROJECT_ROOT.rglob("__pycache__"):
        shutil.rmtree(pycache, ignore_errors=True)
    for pyc in PROJECT_ROOT.rglob("*.pyc"):
        pyc.unlink(missing_ok=True)

    print("\nRuntime state wiped. Starting setup...\n")


def setup(force: bool = False) -> None:
    """Install Python + Node deps and build the frontend."""
    needs_python_env = force or not _venv_exists()
    needs_node_modules = force or not (FRONTEND_DIR / "node_modules").exists()
    needs_frontend_build = force or not DIST_DIR.exists()

    if needs_python_env:
        if _has_uv():
            _run("install python deps", ["uv", "sync", "--all-extras"])
        else:
            _run("create venv", [sys.executable, "-m", "venv", ".venv"])
            _run(
                "install python deps",
                _python_cmd("-m", "pip", "install", "-e", ".[dev,browser]"),
            )

    if needs_node_modules:
        _run("install node deps", ["npm", "install"], cwd=FRONTEND_DIR)

    if needs_frontend_build:
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
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Wipe runtime state (DB, construct docs, SOUL.md) and start from scratch.",
    )
    parser.add_argument("--dev", action="store_true", help="Run API reload + Vite dev UI.")
    parser.add_argument("--boot", action="store_true", help="Run First Light before starting.")
    args = parser.parse_args()

    if args.fresh:
        fresh_clean()
        setup(force=True)
    elif not args.no_setup:
        setup(force=args.setup)

    if args.boot:
        _run("First Light", _python_cmd("-m", "littleman", "boot"))

    start(dev=args.dev)


if __name__ == "__main__":
    main()
