"""Helper functions for the API."""

import base64
from typing import Callable, List

import joppy.data_types as dt


def encode_base64(filepath: str) -> str:
    """Encode an arbitrary file to base64."""
    with open(filepath, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")


def _unpaginate(
    func: Callable[..., dt.DataList[dt.T]], **query: dt.JoplinTypes
) -> List[dt.T]:
    """Calls an Joplin endpoint until it's response doesn't contain more data."""
    response = func(**query)
    items = response.items
    page = 1  # pages are one based
    while response.has_more:
        page += 1
        query["page"] = page
        response = func(**query)
        items.extend(response.items)
    return items
