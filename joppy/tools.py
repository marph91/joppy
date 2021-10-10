"""Helper functions for the API."""

import base64


def encode_base64(filepath: str) -> str:
    """Encode an arbitrary file to base64."""
    with open(filepath, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")
