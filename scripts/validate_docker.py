from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request

IMAGE = "base-navigator:local-verify"
CONTAINER = "base-navigator-local-verify"
HOST_PORT = "18080"


def main() -> int:
    if shutil.which("docker") is None:
        print("Docker CLI not found; skipping local Docker validation.")
        return 2
    if not docker_daemon_available():
        print("Docker daemon is not available; skipping local Docker validation.")
        return 2

    run(["docker", "build", "-t", IMAGE, "."])
    cleanup_container()
    try:
        run(
            [
                "docker",
                "run",
                "-d",
                "--rm",
                "--name",
                CONTAINER,
                "-p",
                f"{HOST_PORT}:8000",
                "-e",
                "APP_ENV=production",
                "-e",
                "ALLOWED_ORIGINS=http://localhost:18080",
                "-e",
                "RATE_LIMIT_ENABLED=false",
                "-e",
                "REDIS_URL=",
                "-e",
                "GEMINI_API_KEY=",
                IMAGE,
            ]
        )
        health = wait_for_health(f"http://127.0.0.1:{HOST_PORT}/health")
        assert health["status"] == "ok"
        assert health["environment"] == "production"
        assert health["rate_limit_enabled"] is False
        assert health["request_id_enabled"] is True
        print(json.dumps({"docker_validation": "passed", "health": health}, indent=2))
        return 0
    finally:
        cleanup_container()


def run(command: list[str]) -> None:
    subprocess.run(command, check=True)


def docker_daemon_available() -> bool:
    result = subprocess.run(
        ["docker", "info"],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


def cleanup_container() -> None:
    subprocess.run(
        ["docker", "rm", "-f", CONTAINER],
        check=False,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def wait_for_health(url: str) -> dict:
    deadline = time.time() + 45
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=3) as response:
                return json.loads(response.read().decode("utf-8"))
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            last_error = exc
            time.sleep(1)
    raise RuntimeError(f"Health check failed: {last_error}")


if __name__ == "__main__":
    sys.exit(main())
