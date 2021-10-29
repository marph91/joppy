"""Module for setting up a joplin instance."""

import json
import os
import stat
import subprocess
import time
from typing import Any, Callable, Optional

import requests
from xvfbwrapper import Xvfb


def download_joplin(destination: str) -> None:
    """Download the joplin desktop app if not already done."""
    if not os.path.exists(destination):
        # TODO: How to download the latest release?
        response = requests.get(
            "https://github.com/laurent22/joplin/releases/download/v2.5.4/"
            "Joplin-2.5.4.AppImage"
        )
        response.raise_for_status()
        with open(destination, "wb") as outfile:
            outfile.write(response.content)
    if not os.access(destination, os.X_OK):
        # add the executable flag
        os.chmod(destination, os.stat(destination).st_mode | stat.S_IEXEC)


def configure_webclipper_autostart(profile: str) -> None:
    """
    Configure the webclipper to start at the first autostart.
    See: https://discourse.joplinapp.org/t/how-to-start-webclipper-headless/20789/4
    """
    webclipper_setting = "clipperServer.autoStart"
    settings_file = f"{profile}/settings.json"

    os.makedirs(profile, exist_ok=True)
    if os.path.exists(settings_file):
        with open(settings_file) as infile:
            settings = json.loads(infile.read())
        if settings.get(webclipper_setting, False):
            return  # autostart is already activated

    # set webclipper autostart setting
    with open(settings_file, "w") as outfile:
        json.dump({webclipper_setting: True, "locale": "en_US"}, outfile)


def wait_for(func: Callable[..., Any], interval: float = 0.5, timeout: int = 5) -> Any:
    """Wait for an arbitrary function to return not None."""
    mustend = time.time() + timeout
    while time.time() < mustend:
        result = func()
        if result is not None:
            return result
        time.sleep(interval)
    raise TimeoutError(f"Function didn't return a valid value {result}.")


class JoplinApp:
    """Represents a joplin application."""

    def __init__(self, app_path: str, profile: str = "test_profile"):
        self.xvfb = xvfb = Xvfb()
        xvfb.start()

        configure_webclipper_autostart(profile)
        self.joplin_process = subprocess.Popen(
            [app_path, "--profile", profile, "--no-welcome"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        # Get the api token from the settings file. Might break at some time,
        # but is the most convenient for now.
        def get_token() -> Optional[str]:
            with open(f"{profile}/settings.json") as infile:
                settings = json.loads(infile.read())
            api_token: Optional[str] = settings.get("api.token")
            return api_token

        self.api_token = wait_for(get_token, timeout=20)

        # Wait until the API is available.
        # TODO: hardcoded url
        def api_available() -> Optional[bool]:
            try:
                response = requests.get("http://localhost:41184/ping")
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
        self.joplin_process.wait()
