# joppy

Python interface for the [Joplin data API](https://joplinapp.org/api/references/rest_api/) (client) and the Joplin server API.

[![build](https://github.com/marph91/joppy/actions/workflows/build.yml/badge.svg)](https://github.com/marph91/joppy/actions/workflows/build.yml)
[![lint](https://github.com/marph91/joppy/actions/workflows/lint.yml/badge.svg)](https://github.com/marph91/joppy/actions/workflows/lint.yml)
[![tests](https://github.com/marph91/joppy/actions/workflows/tests.yml/badge.svg)](https://github.com/marph91/joppy/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/marph91/joppy/branch/master/graph/badge.svg?token=97E6IX792A)](https://codecov.io/gh/marph91/joppy)

[![https://img.shields.io/badge/Joplin-3.5.12-blueviolet](https://img.shields.io/badge/Joplin-3.5.12-blueviolet)](https://github.com/laurent22/joplin)
[![Python version](https://img.shields.io/pypi/pyversions/joppy.svg)](https://pypi.python.org/pypi/joppy/)

## Features

|     | Client API Wrapper | Server API Wrapper |
| --- | --- | --- |
| **Supported** | All functions from the [data API](https://joplinapp.org/help/api/references/rest_api/) | Some reverse engineered functions with a similar interface like the client API wrapper. See the example below and the source code for details. |
| **Not Supported** | -  | - Encryption <br>- Some functions that were either to complex or I didn't see a use for automation. |

## :computer: Installation

From pypi:

```bash
pip install joppy
```

From source:

```bash
git clone https://github.com/marph91/joppy.git
cd joppy
pip install .
```

## :wrench: Usage

Please backup your data before use!

### General function description

- `add_<type>()`: Create a new element.
- `delete_<type>()`: Delete an element by ID.
- `get_<type>()`: Get an element by ID.
- `get_all_<type>()`: Get all elements of a kind.
- `modify_<type>()`: Modify an elements property by ID.
- `search_all()`: Search elements using [joplins search engine](https://joplinapp.org/api/references/rest_api/#searching).

For details, consult the [implementation](joppy/api.py), [joplin documentation](https://joplinapp.org/api/references/rest_api/) or [create an issue](https://github.com/marph91/joppy/issues).

## :bulb: Example snippets

### Client API

Start joplin and [get your API token](https://joplinapp.org/api/references/rest_api/#authorisation). Click to expand the examples.

<details>
<summary>Get all notes</summary>

```python name=get_all_notes
from joppy.client_api import ClientApi

# Create a new Api instance.
api = ClientApi(token=YOUR_TOKEN)

# Get all notes. Note that this method calls get_notes() multiple times to assemble the unpaginated result.
notes = api.get_all_notes(fields="title,id,parent_id,body")

for note in notes:
    print(note)
```

</details>

<details>
<summary>Add a tag to a note</summary>
  
```python name=add_tag_to_note
from joppy.client_api import ClientApi

# Create a new Api instance.

api = ClientApi(token=YOUR_TOKEN)

# Add a notebook.

notebook_id = api.add_notebook(title="My first notebook")

# Add a note in the previously created notebook.

note_id = api.add_note(title="My first note", body="With some content", parent_id=notebook_id)

# Add a tag, that is not yet attached to a note.

tag_id = api.add_tag(title="introduction")

# Link the tag to the note.

api.add_tag_to_note(tag_id=tag_id, note_id=note_id)

````

</details>

<details>
<summary>Add a resource to a note</summary>

```python name=add_resource_to_note
from joppy.client_api import ClientApi
from joppy import tools

# Create a new Api instance.
api = ClientApi(token=YOUR_TOKEN)

# Add a notebook.
notebook_id = api.add_notebook(title="My first notebook")

# Option 1: Add a note with an image data URL. This works only for images.
image_data = tools.encode_base64("path/to/image.png")
api.add_note(
    title="My first note",
    image_data_url=f"data:image/png;base64,{image_data}",
)

# Option 2: Create note and resource separately. Link them later. This works for arbitrary attachments.
note_id = api.add_note(title="My second note")
resource_id = api.add_resource(filename="path/to/image.png", title="My first resource")
api.add_resource_to_note(resource_id=resource_id, note_id=note_id)
````

</details>

<details>
<summary>Bulk remove tags</summary>

Inspired by <https://discourse.joplinapp.org/t/bulk-tag-delete-python-script/5497/1>.

```python name=remove_tags
import re

from joppy.client_api import ClientApi

# Create a new Api instance.
api = ClientApi(token=YOUR_TOKEN)

# Iterate through all tags.
for tag in api.get_all_tags():

    # Delete all tags that match the regex. I. e. start with "!".
    if re.search("^!", tag.title) is not None:
        api.delete_tag(tag.id)
```

</details>

<details>
<summary>Remove unused tags</summary>

Reference: <https://discourse.joplinapp.org/t/prune-empty-tags-from-web-clipper/36194>

```python name=remove_unused_tags
from joppy.client_api import ClientApi

# Create a new Api instance.
api = ClientApi(token=YOUR_TOKEN)

for tag in api.get_all_tags():
    notes_for_tag = api.get_all_notes(tag_id=tag.id)
    if len(notes_for_tag) == 0:
        print("Deleting tag:", tag.title)
        api.delete_tag(tag.id)
```

</details>

<details>
<summary>Remove spaces from tags</summary>

Reference: <https://www.reddit.com/r/joplinapp/comments/pozric/batch_remove_spaces_from_all_tags/>

```python name=remove_spaces_from_tags
import re

from joppy.client_api import ClientApi

# Create a new Api instance.
api = ClientApi(token=YOUR_TOKEN)

# Define the conversion function.
def to_camel_case(name: str) -> str:
    name = re.sub(r"(_|-)+", " ", name).title().replace(" ", "")
    return "".join([name[0].lower(), name[1:]])

# Iterate through all tags and apply the conversion.
for tag in api.get_all_tags():
    api.modify_tag(id_=tag.id, title=to_camel_case(tag.title))
```

</details>

<details>
<summary>Remove orphaned resources</summary>

Inspired by <https://discourse.joplinapp.org/t/joplin-vacuum-a-python-script-to-remove-orphaned-resources/19742>.
Note: The note history is not considered. See: <https://discourse.joplinapp.org/t/joplin-vacuum-a-python-script-to-remove-orphaned-resources/19742/13>.

```python name=remove_orphaned_resources
import re

from joppy.client_api import ClientApi

# Create a new Api instance.
api = ClientApi(token=YOUR_TOKEN)

# Getting the referenced resource directly doesn't work:
# https://github.com/laurent22/joplin/issues/4535
# So we have to find the referenced resources by regex.

# Iterate through all notes and find the referenced resources.
referenced_resources = set()
for note in api.get_all_notes(fields="id,body"):
    matches = re.findall(r"\[.*\]\(:.*\/([A-Za-z0-9]{32})\)", note.body)
    referenced_resources.update(matches)

assert len(referenced_resources) > 0, "sanity check"

for resource in api.get_all_resources():
    if resource.id not in referenced_resources:
        print("Deleting resource:", resource.title)
        api.delete_resource(resource.id)
```

</details>

For more usage examples, check the example scripts or [tests](test/test_client_api.py).

### Server API

The server API should work similarly to the client API in most cases. **Be aware that the server API is experimental and may break at any time. I can't provide any help at sync issues or lost data. Make sure you have a backup and know how to restore it.**

```python
from joppy.server_api import ServerApi

# Create a new Api instance.
api = ServerApi(user="admin@localhost", password="admin", url="http://localhost:22300")

# Acquire a lock.
with api.sync_lock():

    # Add a notebook.
    notebook_id = api.add_notebook(title="My first notebook")

    # Add a note in the previously created notebook.
    note_id = api.add_note(title="My first note", body="With some content", parent_id=notebook_id)
```

## :newspaper: Examples

Before using joppy, you should check the [Joplin plugins](https://joplinapp.org/plugins/). They are probably more convenient. However, if you need a new feature or just want to code in python, you can use joppy.

### Apps

| App | Description |
| --- | --- |
| [jimmy](https://github.com/marph91/jimmy) | A tool to import your notes to Joplin |
| [joplin-sticky-notes](https://github.com/marph91/joplin-sticky-notes) | Stick your Joplin notes to the desktop |
| [joplin-vieweb](https://github.com/joplin-vieweb/django-joplin-vieweb) | A simple web viewer for Joplin |

### Scripts

| Script                                                              | Description                                                                                                                  |
| ------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------- |
| [custom_export.py](examples/custom_export.py)                       | Export resources next to notes, instead of a separate folder.                                                                |
| [note_export.py](examples/note_export.py)                           | Export notes to any format supported by [pandoc](https://pandoc.org/).                                                       |
| [note_stats.py](examples/note_stats.py)                             | Get some simple statistics about your notes, based on [nltk](https://www.nltk.org/).                                         |
| [note_tree_export.py](examples/note_tree_export.py)                 | Joplin only supports PDF export of a single note. This script allows to export one, multiple or all notebooks to PDF or TXT. |
| [visualize_note_locations.py](examples/visualize_note_locations.py) | Visualize the locations of your notes.                                                                                       |
| [joplin-ui-tests](https://github.com/marph91/joplin-ui-tests)       | System tests for the joplin desktop app. Based on selenium.                                                                  |

## :sunny: Tests

To run the tests, some additional system packages and python modules are needed. After installing them, just run:

```bash
python -m unittest
```

It's possible to configure the test run via some environment variables:

- `SLOW_TESTS`: Set this variable to run the slow tests. Default not set.
- `API_TOKEN`: Set this variable if there is already a joplin instance running. **Don't use your default joplin profile!** By default, a joplin instance is started inside xvfb. This takes some time, but works for CI.

## :book: Changelog

The changelog for versions greater than 1.0.0 can be found at the [releases page](https://github.com/marph91/joppy/releases).

### 1.0.0

- Rename the client API. It should be used by `from joppy.client_api import ClientApi` instead of `from joppy.client_api import ClientApi` now.
- Add support for the server API (<https://github.com/marph91/joppy/pull/27>). It should be used by `from joppy.server_api import ServerApi`.

### 0.2.3

- Don't use the root logger for logging.
- Add support for [revisions](https://joplinapp.org/help/api/references/rest_api/#revisions).

### 0.2.2

- Fix adding non-image ressources (<https://github.com/marph91/joppy/issues/24>).
- Cast `markup_language` to an appropriate enum type.
- Add changelog.

### 0.2.1

- Fix PDF output example (<https://github.com/marph91/joppy/issues/19>).
- :warning: Drop tests for python 3.6, since it's EOL. It may still work.
- Fix the type of `todo_completed` and `todo_due`. They are a unix timestamp, not a bool.

### 0.1.1

- Add typing support to the pypi module.

### 0.1.0

- Use a requests session for speedup (<https://github.com/marph91/joppy/issues/15>).
- :warning: Convert the API responses to data objects (<https://github.com/marph91/joppy/pull/17>). Main difference is to use `note.id` instead of `note["id"]` for example.

### 0.0.7

- Fix getting the binary resource file (<https://github.com/marph91/joppy/issues/13>).

### 0.0.6

- Add convenience method for deleting all notes.
- Add example scripts.

### 0.0.5

- Fix package publishing workflow.

### 0.0.4

- Add support for python 3.6 and 3.7.

### 0.0.3

- Fix search with special characters (<https://github.com/marph91/joppy/issues/5>).
- Remove arbitrary arguments from the internal base requests, since they aren't needed and may cause bugs.

### 0.0.2

- CI and test improvements.
- Move complete setup to `setup.cfg`.

### 0.0.1

- Initial release.
