"""
Replace the body of Joplin notes with the content of Markdown files.
Match the Joplin note titles with the Markdown filenames.

Requirements: pip install joppy
Usage: python overwrite_same_title_notes.py path/to/markdown/folder --api-token XYZ

Reference: https://discourse.joplinapp.org/t/overwrite-existing-note-and-preserve-existing-links/45897
"""

import argparse
import logging
import os
from pathlib import Path
import sys

from joppy.client_api import ClientApi


logging.basicConfig(
    format="%(asctime)s [%(levelname)s]: %(message)s",
    stream=sys.stdout,
    level=logging.INFO,
)


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("source_folder", type=Path)
    parser.add_argument("--api-token", default=os.getenv("API_TOKEN"))
    return parser.parse_args()


def main():
    args = parse_args()

    api = ClientApi(token=args.api_token)

    # Scan through the source folder and get all Markdown files.
    for file_ in args.source_folder.rglob("*.md"):

        # Search for the filename in Joplin.
        candidates = api.search_all(query=f'title:"{file_.stem}"')

        # Evaluate the search results.
        match len(candidates):
            case 0:
                logging.warning(
                    f'Could not find a Joplin note for Markdown file "{file_.stem}".'
                )
                continue
            case 1:
                note_to_replace = candidates[0]
            case too_many:
                logging.warning(
                    f'Found {too_many} Joplin notes for Markdown file "{file_.stem}". Selecting the first one.'
                )
                note_to_replace = candidates[0]

        # Finally replace the note body.
        api.modify_note(note_to_replace.id, body=file_.read_text(encoding="utf-8"))
        logging.info(f'Replaced body of note "{file_.stem}".')


if __name__ == "__main__":
    main()
