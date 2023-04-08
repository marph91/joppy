"""
Remove geolocation info from all notes.

Requirements: pip install joppy

Usage: API_TOKEN=XYZ python remove_geolocation_info.py

Reference:
- https://discourse.joplinapp.org/t/how-to-remove-all-geolocation-info/8369
"""

import os

from joppy.api import Api

# Create a new Api instance.
api = Api(token=os.getenv("API_TOKEN"))

# Iterate through all notes.
location_keys = ["longitude", "latitude", "altitude"]
for note in api.get_all_notes(fields=",".join(["id"] + location_keys)):

    # Set location info to 0 if different.
    if any(getattr(note, location_key) != 0 for location_key in location_keys):
        api.modify_note(
            id_=note.id, **{location_key: 0 for location_key in location_keys}
        )
