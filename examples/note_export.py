"""
Convert notes to any format supported by pandoc.

Requirements:
- pip install joppy pypandoc weasyprint
- pandoc (https://github.com/NicklasTegner/pypandoc#installing-pandoc)

Usage:
- API_TOKEN=XYZ python note_export.py
- python note_export.py --help

There are also other pdf engines for pdf export, like pdflatex:
https://pandoc.org/MANUAL.html#option--pdf-engine
apt install texlive-latex-base texlive-fonts-recommended texlive-fonts-extra
"""

import argparse
import os
import tempfile

from joppy.api import Api
import pypandoc


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "note_titles",
        nargs="+",
        help="Title of the notes to convert.",
    )
    parser.add_argument(
        "--output-format",
        default="pdf",
        help="Output format. For supported formats, see "
        "https://pandoc.org/MANUAL.html#general-options.",
    )
    parser.add_argument(
        "--output-folder",
        default="note_export",
        help="Output folder for all notes.",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Obtain the notes via joplin API.
    api = Api(token=os.getenv("API_TOKEN"))
    notes = api.get_all_notes(fields="id,title")

    # Find notes with matching titles.
    candidates = []
    for title in args.note_titles:
        candidates.extend([note for note in notes if note.title == title])
    print(f"Found {len(candidates)} matching notes.")

    # Create a temporary directory for the resources.
    with tempfile.TemporaryDirectory() as tmpdirname:

        # Convert all notes to the specified format.
        os.makedirs(args.output_folder, exist_ok=True)
        for candidate in candidates:
            note = api.get_note(id_=candidate.id, fields="body")
            note_body = note.body

            # Download and add all image resources
            resources = api.get_all_resources(note_id=candidate.id, fields="id,mime")
            for resource in resources:
                if not resource.mime.startswith("image"):
                    continue
                resource_binary = api.get_resource_file(resource.id)
                with open(f"{tmpdirname}/{resource.id}", "wb") as outfile:
                    outfile.write(resource_binary)
                # Replace joplin's local link with the path to the just
                # downloaded resource.
                note_body = note_body.replace(
                    f":/{resource.id}", f"{tmpdirname}/{resource.id}"
                )

            title_normalized = (
                candidate.title.lower().replace(" ", "_") + "_" + candidate.id
            )
            output_path = (
                f"{args.output_folder}/{title_normalized}.{args.output_format}"
            )

            valid_output_formats = pypandoc.get_pandoc_formats()[1]
            if args.output_format not in valid_output_formats:
                raise ValueError(
                    f"Invalid format: {args.output_format}. "
                    f"Valid formats: {valid_output_formats}."
                )
            # special arguments for some output formats
            format_kwargs = {
                # https://github.com/NicklasTegner/pypandoc/issues/186#issuecomment-673282133
                "pdf": {
                    "to": "html",
                    "extra_args": [
                        "--pdf-engine",
                        "weasyprint",
                        "--metadata",
                        f"title={candidate.title}",
                    ],
                }
            }

            pypandoc.convert_text(
                note_body,
                format="md",
                outputfile=output_path,
                **format_kwargs.get(args.output_format, {"to": args.output_format}),
            )


if __name__ == "__main__":
    main()
