"""
Export a reddit page including comments to Joplin.
Requirements: pip install joppy markdownify
Usage: API_TOKEN=XYZ python reddit_clipper.py
"""

import os

from bs4 import BeautifulSoup
from joppy.client_api import ClientApi
from markdownify import markdownify as md
import requests


def parse_reddit_page(url):
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64; rv:105.0) Gecko/20100101 Firefox/105.0"
        )
    }
    response = requests.get(url, headers=headers)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    note_body = []

    # parse post
    entry = soup.find("div", class_="entry")

    author = entry.find("a", class_="author")
    title = entry.find("a", class_="title")
    note_title = f"{author.text}: {title.text}"

    body = entry.find("div", class_="md")
    note_body.append(md(str(body)))

    # parse comments
    note_body.append("## Comments\n\n")

    comment_area = soup.find("div", class_="commentarea")
    comments = comment_area.find_all("div", class_="entry")
    for comment in comments:
        comment_author = comment.find("a", class_="author")
        if comment_author is None:
            # This is the "continue thread" element
            continue
        comment_body = comment.find("div", class_="md")
        note_body.append(f"**{comment_author.text}**: {md(str(comment_body))}")

    return note_title, "".join(note_body)


def create_joplin_note(note_title, note_body, destination_notebook):
    # Get the token from the environment or hardcode it here.
    # https://joplinapp.org/api/references/rest_api/#authorisation
    joplin_api = ClientApi(token=os.getenv("API_TOKEN"))

    # Search the parent notebook in Joplin.
    notebook_candidates = joplin_api.search(
        query=destination_notebook, type="folder"
    ).items
    if len(notebook_candidates) < 1:
        exit(1)
    else:
        notebook_id = notebook_candidates[0].id

    # Create note in joplin
    joplin_api.add_note(
        title=note_title,
        body=note_body,
        parent_id=notebook_id,
    )


def main():
    destination_notebook = "tmp"
    url = (
        "https://old.reddit.com/r/"
        "joplinapp/comments/xm5xdr/how_do_you_save_reddit_posts_with_comments_in"
    )

    note_title, note_body = parse_reddit_page(url)
    create_joplin_note(note_title, note_body, destination_notebook)


if __name__ == "__main__":
    main()
