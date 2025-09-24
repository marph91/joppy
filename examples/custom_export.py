"""
Custom export for Joplin notes

Details: https://discourse.joplinapp.org/t/feature-request-place-attachments-in-the-same-sub-folder-when-exporting/23072  # noqa
Requirements: pip install joppy
Usage: python examples/custom_export.py --api-token xyz
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
import os
from pathlib import Path
import re
from typing import List

from joppy.client_api import ClientApi
import joppy.data_types as dt


def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-folder", default="joplin_note_export")
    parser.add_argument("--api-token", default=os.getenv("API_TOKEN"))
    return parser.parse_args()


@dataclass
class TreeItem:
    """Represents a notebook and its children."""

    data: dt.NotebookData
    child_items: List[TreeItem]
    child_notes: List[dt.NoteData]
    child_resources: List[dt.ResourceData]


def create_notebook_tree(flat_list):
    """
    Create a tree of IDs from a flat list.
    Based on https://stackoverflow.com/a/45461474/7410886.
    """
    graph = {item: set() for item in flat_list}
    roots = []
    for id_, item in flat_list.items():
        parent_id = item.parent_id
        if parent_id:
            graph[parent_id].add(id_)
        else:
            roots.append(id_)

    def traverse(graph, names):
        hierarchy = {}
        for name in names:
            hierarchy[name] = traverse(graph, graph[name])
        return hierarchy

    return traverse(graph, roots)


def create_hierarchy(api):
    """
    Create a notebook hierarchy (including notes and resources)
    from a flat notebook list.
    """
    # Don't use "as_tree=True", since it's undocumented and might be removed.
    notebooks_flat_api = api.get_all_notebooks(fields="id,title,parent_id")
    notebooks_flat_map = {notebook.id: notebook for notebook in notebooks_flat_api}
    notebook_tree_ids = create_notebook_tree(notebooks_flat_map)

    item_count = defaultdict(int)

    def replace_ids_by_items(id_tree):
        item_tree = []
        for key, value in id_tree.items():
            item_count["notebooks"] += 1
            child_notes = api.get_all_notes(notebook_id=key, fields="id,title,body")
            child_resources = []
            for note in child_notes:
                child_resources.extend(
                    api.get_all_resources(note_id=note.id, fields="id,title")
                )

            item_count["notes"] += len(child_notes)
            item_count["resources"] += len(child_resources)
            item_tree.append(
                TreeItem(
                    notebooks_flat_map[key],
                    replace_ids_by_items(value),
                    child_notes,
                    child_resources,
                )
            )
        return item_tree

    notebook_tree_items = replace_ids_by_items(notebook_tree_ids)
    print("Exporting:", item_count)
    return notebook_tree_items


def replacements(value: str) -> str:
    """Replace bad characters in filenames."""
    # https://stackoverflow.com/a/27647173/7410886
    return re.sub(r'[\\/*?:"<>|\s]', "_", value)


def create_files(api, tree, output_dir: Path):
    """
    Go through the notebook tree and create:
    - folders for notebooks
    - markdown files for notes
    - binary files for resources
    """
    output_dir.mkdir(exist_ok=True)


    for item in tree:
        note_links = []
        current_directory = output_dir / replacements(item.data.title)

        create_files(api, item.child_items, current_directory)

        attach_path = current_directory / "_resources"

        attach_path.mkdir(exist_ok=True)


        for resource in item.child_resources:
            resource_binary = api.get_resource_file(id_=resource.id)
            resource_path = attach_path / replacements(
                resource.title or resource.id
            )
            filename = str(resource_path).split('/')[-1]
            note_links.append((f":/{resource.id}", f'_resources/{filename}'))
            try:
                resource_path.write_bytes(resource_binary)
            except Exception as error:
                print(error)

        for note in item.child_notes:
            note_path = (current_directory / replacements(note.title)).with_suffix(
                ".md"
            )
            note_body = note.body
            for needle, replacer in note_links:
                note_body = note_body.replace(needle, replacer)
            try:
                note_path.write_text(note_body, encoding="utf-8")
            except Exception as error:
                print(error)



def main():
    args = parse_args()

    # Obtain the notes via joplin API.
    api = ClientApi(token=args.api_token)

    tree = create_hierarchy(api)
    create_files(api, tree, Path(args.output_folder))


if __name__ == "__main__":
    main()
