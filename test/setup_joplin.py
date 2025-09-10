"""Module for setting up a joplin instance."""

import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import time
from typing import Any, Callable, Optional

import requests
from xvfbwrapper import Xvfb


def download_joplin_client(destination: Path) -> None:
    """Download the latest joplin desktop app release if not already done."""
    if not destination.exists():
        # obtain the version string
        # response = requests.get(
        #    "https://api.github.com/repos/laurent22/joplin/releases"
        # )
        # latest_version = response.json()[0]["name"].lstrip("v")
        latest_version = "3.4.12"
        print(f"Testing with Joplin version {latest_version}.")

        # download the binary
        response = requests.get(
            f"https://github.com/laurent22/joplin/releases/download/v{latest_version}/"
            f"Joplin-{latest_version}.AppImage"
        )
        response.raise_for_status()
        destination.write_bytes(response.content)
    if not os.access(destination, os.X_OK):
        # add the executable flag
        os.chmod(destination, os.stat(destination).st_mode | stat.S_IEXEC)


def configure_webclipper_autostart(profile: Path) -> None:
    """
    Configure the webclipper to start at the first autostart.
    See: https://discourse.joplinapp.org/t/how-to-start-webclipper-headless/20789/4
    """
    profile.mkdir(parents=True, exist_ok=True)

    settings_file = profile / "settings.json"
    if settings_file.exists():
        settings = json.loads(settings_file.read_text(encoding="utf-8"))
    else:
        settings = {}
    settings.update({"clipperServer.autoStart": True, "locale": "en_US"})
    settings_file.write_text(json.dumps(settings), encoding="utf-8")


def wait_for(func: Callable[..., Any], interval: float = 0.5, timeout: int = 5) -> Any:
    """Wait for an arbitrary function to return not None."""
    mustend = time.time() + timeout
    while time.time() < mustend:
        result = func()
        if result is not None:
            return result
        time.sleep(interval)
    raise TimeoutError(f"Function didn't return a valid value {result}.")


class JoplinClient:
    """Represents a joplin client application."""

    def __init__(self, app_path: Path, profile: Path):
        self.xvfb = xvfb = Xvfb()
        xvfb.start()

        configure_webclipper_autostart(profile)
        self.joplin_process = subprocess.Popen(
            # For Ubuntu > 20.04, "--no-sandbox" is needed.
            [str(app_path), "--profile", str(profile), "--no-welcome", "--no-sandbox"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # Get the api token from the settings file. Might break at some time,
        # but is the most convenient for now.
        def get_token() -> Optional[str]:
            settings = json.loads(
                (profile / "settings.json").read_text(encoding="utf-8")
            )
            if self.joplin_process.poll() is not None:
                # Joplin app is not running anymore.
                # https://docs.python.org/3/library/subprocess.html#subprocess.Popen.poll
                stdout, stderr = self.joplin_process.communicate()
                print(stdout, stderr)
            assert settings.get("clipperServer.autoStart", False), (
                "Webclipper should be active"
            )
            api_token: Optional[str] = settings.get("api.token")
            return api_token

        self.api_token = wait_for(get_token, timeout=20)

        # Wait until the API is available.
        # TODO: hardcoded url
        def api_available() -> Optional[bool]:
            try:
                response = requests.get("http://localhost:41184/ping", timeout=5)
                if response.status_code == 200:
                    return True
            except Exception:
                pass
            return None

        wait_for(api_available, timeout=20)

    def stop(self) -> None:
        """Stop the joplin app and the corresponding xvfb."""
        self.xvfb.stop()
        self.joplin_process.terminate()
        self.joplin_process.communicate(timeout=5)
        self.joplin_process.wait(timeout=5)


class JoplinServer:
    """Represents a joplin server."""

    def __init__(self) -> None:
        # Wait until the API is available.
        def api_available() -> Optional[bool]:
            try:
                response = requests.get("http://localhost:22300/api/ping", timeout=5)
                if response.status_code == 200:
                    return True
            except Exception:
                pass
            return None

        # check if server is running already
        if api_available() is not None:
            self.joplin_process = None
            return

        if shutil.which("docker") is None:
            raise Exception("Please install docker and try again.")
        # TODO: Is caching the container in GHA possible?
        self.joplin_process = subprocess.Popen(
            ["docker", "run", "-p", "22300:22300", "joplin/server:latest"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        wait_for(api_available, timeout=600)

    def stop(self) -> None:
        """Stop the joplin server."""
        if self.joplin_process is not None:
            self.joplin_process.terminate()
            self.joplin_process.wait(timeout=5)
