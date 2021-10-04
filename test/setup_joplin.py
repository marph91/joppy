"""Module for setting up a joplin instance."""

import os
import stat
import subprocess
import time

import requests
from xvfbwrapper import Xvfb


def download_joplin(destination: str):
    """Download the joplin desktop app if not already done."""
    if not os.path.exists(destination):
        # TODO: How to download the latest release?
        response = requests.get(
            "https://github.com/laurent22/joplin/releases/download/v2.4.9/Joplin-2.4.9.AppImage"  # noqa: E501
        )
        response.raise_for_status()
        with open(destination, "wb") as outfile:
            outfile.write(response.content)
    if not os.access(destination, os.X_OK):
        # add the executable flag
        os.chmod(destination, os.stat(destination).st_mode | stat.S_IEXEC)


class JoplinApp:
    """Represents a joplin application."""

    def __init__(self, app_path: str):
        self.xvfb = xvfb = Xvfb()
        xvfb.start()

        self.joplin_process = subprocess.Popen(
            [app_path, "--profile", "test_profile", "--no-welcome"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @staticmethod
    def get_token() -> str:
        """
        Get the token from the started instance. See:
        https://joplinapp.org/spec/clipper_auth/#request-it-programmatically
        """
        # start pyautogui inside xvfb
        import pyautogui

        # request an authorization token
        auth_token = None
        while auth_token is None:
            try:
                response = requests.post("http://localhost:41184/auth")
                if response.status_code == 200:
                    auth_token = response.json()["auth_token"]
                else:
                    time.sleep(0.2)
            except requests.exceptions.ConnectionError:
                time.sleep(0.2)

        # find and click the authorization button
        button_location = None
        while button_location is None:
            button_location = pyautogui.locateCenterOnScreen(
                "test/grant_authorization_button.png", confidence=0.9
            )
            time.sleep(0.2)
        pyautogui.click(*button_location)

        # wait until the api token is available
        api_token = None
        while api_token is None:
            response = requests.get(
                f"http://localhost:41184/auth/check?auth_token={auth_token}"
            )
            if response.status_code == 200:
                api_token = response.json()["token"]
            else:
                time.sleep(0.2)

        return api_token

    def stop(self):
        """Stop the joplin app and the corresponding xvfb."""
        self.xvfb.stop()
        self.joplin_process.terminate()
        self.joplin_process.wait()
