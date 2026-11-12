"""Single-instance hosted demo: supervise the API and SQL worker together."""

import os
import signal
import subprocess
import sys
import time

from dotenv import load_dotenv


def validate_environment():
    if not os.getenv("DATABASE_URL", "").startswith(
        ("postgres://", "postgresql://", "postgresql+psycopg2://")
    ):
        raise ValueError("Hosted mode requires persistent PostgreSQL DATABASE_URL")
    if not os.getenv("PAYPOOL_FRONTEND_URL", "").startswith("https://"):
        raise ValueError("Set PAYPOOL_FRONTEND_URL to the exact HTTPS frontend URL")
    if os.getenv("PAYPOOL_COOKIE_SECURE", "false").lower() != "true":
        raise ValueError("Hosted mode requires PAYPOOL_COOKIE_SECURE=true")
    port = int(os.getenv("PORT", "10000"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT must be between 1 and 65535")
    return port


def main():
    load_dotenv()
    port = validate_environment()
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True)
    if os.getenv("PAYPOOL_PREPARE_DEMO", "false").lower() == "true":
        from app.platform.demo_scenarios import prepare
        from app.platform.store import Store

        store = Store()
        manifest = prepare(store)
        print(
            "Prepared demo dates:",
            {k: v["date"] for k, v in manifest["scenarios"].items()},
            flush=True,
        )
        store.engine.dispose()
    children = []
    stopping = False

    def stop(signum=None, frame=None):
        nonlocal stopping
        stopping = True
        for child in children:
            if child.poll() is None:
                child.terminate()

    signal.signal(signal.SIGTERM, stop)
    signal.signal(signal.SIGINT, stop)
    code = 0
    try:
        for command in (
            [
                sys.executable,
                "-m",
                "uvicorn",
                "app.main:app",
                "--host",
                "0.0.0.0",
                "--port",
                str(port),
            ],
            [sys.executable, "-m", "app.platform.worker", "--interval", "30"],
        ):
            children.append(subprocess.Popen(command))
        while not stopping:
            if any(child.poll() is not None for child in children):
                print("API or worker exited; stopping the hosted service", flush=True)
                code = 1
                break
            time.sleep(1)
    finally:
        stop()
        for child in children:
            try:
                child.wait(timeout=10)
            except subprocess.TimeoutExpired:
                child.kill()
                child.wait()
    return code


if __name__ == "__main__":
    raise SystemExit(main())
