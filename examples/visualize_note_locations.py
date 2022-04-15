"""
Visualize the location of your Joplin notes.
Requirements: pip install joppy pandas plotly
Usage: API_TOKEN=XYZ python visualize_note_locations.py
"""

import os

from joppy.api import Api
import pandas as pd
import plotly.express as px


api = Api(token=os.getenv("API_TOKEN"))
notes = api.get_all_notes(fields="id,title,latitude,longitude")
print("Notes:", len(notes))

# filter notes with location (0, 0)
notes = [note for note in notes if note["latitude"] != 0 and note["longitude"] != 0]

df = pd.DataFrame(notes)
fig = px.scatter_geo(df, lat="latitude", lon="longitude", hover_name="title")
fig.update_layout(
    title="Note Locations",
    title_x=0.5,
    geo_scope="europe",
)
fig.show()
