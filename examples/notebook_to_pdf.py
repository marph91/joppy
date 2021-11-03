"""
Convert a notebook and it's notes to PDF. Doesn't work recursively.

Requirements: pip install markdown2 weasyprint
Usage: API_TOKEN=XYZ python notebook_to_pdf.py --title "your notebook title"
"""

import argparse
import os

from joppy.api import Api
from markdown2 import Markdown
from weasyprint import HTML


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--title", default="*", help="Title of the notebook in joplin.")
    parser.add_argument(
        "--output-file",
        default="joplin_notebook.pdf",
        help="Path to the PDF output file.",
    )
    args = parser.parse_args()

    # Obtain the notebook and notes via joplin API.
    api = Api(token=os.getenv("API_TOKEN"))
    notebooks = api.search_all(query=args.title, type="folder", fields="id,title")
    if len(notebooks) != 1:
        raise Exception(f"{len(notebooks)} notebooks found. Expected exactly one.")
    notes = api.get_all_notes(notebook_id=notebooks[0]["id"], fields="title,body")

    # Convert the notes to HTML and merge them to a single document.
    html_parts = [f"<h1>{notebooks[0]['title']}</h1>"]
    markdowner = Markdown(extras=["break-on-newline"])
    for note in notes:
        html_parts.append(markdowner.convert(f"<h2>{note['title']}</h2>{note['body']}"))
    html_complete = "".join(html_parts)

    # Convert the HTML document to PDF.
    HTML(string=html_complete).write_pdf(args.output_file)


if __name__ == "__main__":
    main()
