"""
Convert notebooks and notes to HTML, PDF or TXT.

Requirements (for pdf export): pip install joppy markdown weasyprint

Usage:
- API_TOKEN=XYZ python note_tree_export.py --output note_tree.txt
- python note_tree_export.py --help

Known issues:
- Checkboxes don't get visualized correctly.
- Big tables are truncated.

Reference:
- https://discourse.joplinapp.org/t/request-pdf-export-for-notebook-or-serveral-marked-notes/5648
- https://discourse.joplinapp.org/t/list-of-folders-notes-something-like-treeview/29051
"""

import argparse
import dataclasses
import os
from pathlib import Path

from joppy.api import Api


# "frozen", because the class needs to be hashable for creating the tree.
# "order" to allow sorting.
@dataclasses.dataclass(order=True, frozen=True)
class Note:
    """Represents a Joplin note."""

    id: str
    parent_id: str
    title: str
    body: str

    def ___lt__(self, other):
        return self.title < other.title


@dataclasses.dataclass(order=True, frozen=True)
class Notebook:
    """Represents a Joplin notebook."""

    id: str
    parent_id: str
    title: str

    def ___lt__(self, other):
        return self.title < other.title


def create_tree(flat_list):
    """
    Create a tree of IDs from a flat list.
    Based on https://stackoverflow.com/a/45461474/7410886.
    """
    graph = {item: set() for item in flat_list}
    roots = []
    for id_, item in flat_list.items():
        parent_id = "nb" * bool(item.parent_id) + item.parent_id
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


def get_item_tree(api):
    """
    Generate an item tree from the Joplin API. The API returns a flat list of
    items with parent child relations.
    """
    # Notebooks and notes have the same namespaces for IDs.
    # Thus the following convention for generating the tree:
    # - Notebook IDs get the prefix "nb"
    # - Note IDs get the prefix "n"
    notebooks_flat_api = api.get_all_notebooks(fields="id,parent_id,title")
    notebooks_flat = {
        "nb" + nb.id: Notebook(nb.id, nb.parent_id, nb.title)
        for nb in notebooks_flat_api
    }
    notes_flat_api = api.get_all_notes(fields="id,parent_id,title,body")
    notes_flat = {
        "n" + n.id: Note(n.id, n.parent_id, n.title, n.body) for n in notes_flat_api
    }

    id_item_mapping = {**notebooks_flat, **notes_flat}
    id_tree = create_tree(id_item_mapping)

    def replace_ids_by_items(id_tree):
        item_tree = {}
        for key, value in id_tree.items():
            item_tree[id_item_mapping[key]] = replace_ids_by_items(value)
        return item_tree

    return replace_ids_by_items(id_tree)


def item_tree_to_html(item_tree):
    """Convert the notes to HTML and merge them to a single document."""
    from markdown import Markdown

    md = Markdown(extensions=["nl2br", "sane_lists", "tables"])

    def sub_tree_to_html(item_tree, level=1):
        next_level = level + 1
        html_parts = []
        for key, value in item_tree.items():
            if isinstance(key, Notebook):
                html_parts.append(f"<h{level}>{key.title}</h{level}>\n")
            else:
                # Prevent wrong title hierarchy.
                body = key.body.replace("# ", "#" * level + " ")
                html_parts.append(
                    md.convert(f"<h{level}>{key.title}</h{level}>\n{body}\n")
                )
            html_parts.extend(sub_tree_to_html(value, next_level))
        return html_parts

    return "".join(sub_tree_to_html(item_tree))


def item_tree_to_txt(item_tree):
    def sub_tree_to_txt(item_tree, level=0):
        next_level = level + 1
        txt_parts = []
        for key, value in item_tree.items():
            if isinstance(key, Notebook):
                txt_parts.append(f"{'  ' * level}* {key.title}")
            else:
                txt_parts.append(f"{'  ' * level}- {key.title}")
            txt_parts.extend(sub_tree_to_txt(value, next_level))
        return txt_parts

    return "\n".join(sub_tree_to_txt(item_tree))


def sort_item_tree(item_tree):
    """Sort all items based on their title."""
    return {
        key: sort_item_tree(value) if isinstance(value, dict) else value
        for key, value in sorted(item_tree.items(), key=lambda item: item[0].title)
    }


def select_notebook(item_tree, query, by="title"):
    """Find a notebook in the complete item tree."""
    for key, value in item_tree.items():
        if isinstance(key, Notebook) and getattr(key, by) in query:
            yield key, value
        yield from select_notebook(value, query)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--notebooks",
        nargs="+",
        help="Title of the root notebooks. By default all notebooks are selected.",
    )
    parser.add_argument("--output", help="Path to the output file.")
    args = parser.parse_args()

    output_format = Path(args.output).suffix
    if output_format not in (".html", ".pdf", ".txt"):
        raise ValueError(f"Unsupported format '{output_format}'")

    # Obtain the notebooks and notes via joplin API.
    api = Api(token=os.getenv("API_TOKEN"))
    item_tree = get_item_tree(api)

    if args.notebooks:
        item_tree = dict(select_notebook(item_tree, args.notebooks))
        if not item_tree:
            raise Exception(
                "No notebooks found. Please specify at least one valid notebook."
            )
    sorted_item_tree = sort_item_tree(item_tree)

    if output_format in (".html", ".pdf"):

        html = item_tree_to_html(sorted_item_tree)

        if output_format == ".html":
            with open(args.output, "w") as outfile:
                outfile.write(html)
        else:
            from weasyprint import HTML

            HTML(string=html).write_pdf(args.output)

    if output_format == ".txt":
        txt_tree = item_tree_to_txt(sorted_item_tree)
        with open(args.output, "w") as outfile:
            outfile.write(txt_tree)


if __name__ == "__main__":
    main()
