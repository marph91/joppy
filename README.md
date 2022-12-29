# joppy

Python interface for the [Joplin data API](https://joplinapp.org/api/references/rest_api/).

[![build](https://github.com/marph91/joppy/actions/workflows/build.yml/badge.svg)](https://github.com/marph91/joppy/actions/workflows/build.yml)
[![lint](https://github.com/marph91/joppy/actions/workflows/lint.yml/badge.svg)](https://github.com/marph91/joppy/actions/workflows/lint.yml)
[![tests](https://github.com/marph91/joppy/actions/workflows/tests.yml/badge.svg)](https://github.com/marph91/joppy/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/marph91/joppy/branch/master/graph/badge.svg?token=97E6IX792A)](https://codecov.io/gh/marph91/joppy)

[![https://img.shields.io/badge/Joplin-2.9.17-blueviolet](https://img.shields.io/badge/Joplin-2.9.17-blueviolet)](https://github.com/laurent22/joplin)
[![Python version](https://img.shields.io/pypi/pyversions/joppy.svg)](https://pypi.python.org/pypi/joppy/)

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

### General function description

- `add_<type>()`: Create a new element.
- `delete_<type>()`: Delete an element by ID.
- `get_<type>()`: Get an element by ID.
- `get_all_<type>()`: Get all elements of a kind.
- `modify_<type>()`: Modify an elements property by ID.
- `search_all()`: Search elements using [joplins search engine](https://joplinapp.org/api/references/rest_api/#searching).

For details, consult the [implementation](joppy/api.py), [joplin documentation](https://joplinapp.org/api/references/rest_api/) or [create an issue](https://github.com/marph91/joppy/issues).

## :bulb: Example snippets

Start joplin and [get your API token](https://joplinapp.org/api/references/rest_api/#authorisation). Click to expand the examples.

<details>
<summary>Get all notes</summary>

```python name=get_all_notes
from joppy.api import Api

# Create a new Api instance.
api = Api(token=YOUR_TOKEN)

# Get all notes. Note that this method calls get_notes() multiple times to assemble the unpaginated result.
notes = api.get_all_notes()
```

</details>

<details>
<summary>Add a tag to a note</summary>
  
```python name=add_tag_to_note
from joppy.api import Api

# Create a new Api instance.

api = Api(token=YOUR_TOKEN)

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
from joppy.api import Api
from joppy import tools

# Create a new Api instance.
api = Api(token=YOUR_TOKEN)

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

from joppy.api import Api

# Create a new Api instance.
api = Api(token=YOUR_TOKEN)

# Iterate through all tags.
for tag in api.get_all_tags():

    # Delete all tags that match the regex. I. e. start with "!".
    if re.search("^!", tag.title) is not None:
        api.delete_tag(tag.id)
```

</details>

<details>
<summary>Remove spaces from tags</summary>

Inspired by <https://www.reddit.com/r/joplinapp/comments/pozric/batch_remove_spaces_from_all_tags/>.

```python name=remove_spaces_from_tags
import re

from joppy.api import Api

# Create a new Api instance.
api = Api(token=YOUR_TOKEN)

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

from joppy.api import Api

# Create a new Api instance.
api = Api(token=YOUR_TOKEN)

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
        print("Deleting resource:", resource)
        api.delete_resource(resource.id)
```

</details>

For more usage examples, check the example scripts or [tests](test/test_api.py).

## :newspaper: Example scripts

Before using joppy, you should check the [Joplin plugins](https://joplinapp.org/plugins/). They are probably more convenient. However, if you need a new feature or just want to code in python, you can use joppy. Below are example scripts to showcase how joppy can be used.

| Script                                                              | Description                                                                                                           |
| ------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| [note_export.py](examples/note_export.py)                           | Export notes to any format supported by [pandoc](https://pandoc.org/).                                                |
| [note_stats.py](examples/note_stats.py)                             | Get some simple statistics about your notes, based on [nltk](https://www.nltk.org/).                                  |
| [pdf_export.py](examples/pdf_export.py)                             | Joplin only supports PDF export of a single note. This script allows to export one, multiple or all notebooks to PDF. |
| [visualize_note_locations.py](examples/visualize_note_locations.py) | Visualize the locations of your notes.                                                                                |
| <https://github.com/marph91/joplin-ui-tests>                        | System tests for the joplin desktop app. Based on selenium.                                                           |
| <https://github.com/gri38/django-joplin_vieweb>                     | Web viewer for joplin.                                                                                                |
| <https://github.com/BeneKurz/Toodledo2Joplin>                       | Import notes from <https://www.toodledo.com> to Joplin.                                                               |

## :sunny: Tests

To run the tests, some additional system packages and python modules are needed. After installing them, just run:

```bash
python -m unittest
```

It's possible to configure the test run via some environment variables:

- `SLOW_TESTS`: Set this variable to run the slow tests. Default not set.
- `API_TOKEN`: Set this variable if there is already a joplin instance running. **Don't use your default joplin profile!** By default, a joplin instance is started inside xvfb. This takes some time, but works for CI.

## :question: FAQ

Short summary about questions I had during the implementation.

- What is the purpose/usecase of "user_created_time"? Isn't "created_time" sufficient? &#8594; <https://discourse.joplinapp.org/t/importing-notes-from-tiddlywiki-api-feature-request-for-timestamps/1952/7>
- Why is the token in the query? &#8594; <https://discourse.joplinapp.org/t/joplin-api-token-in-header-vs-query-parameters/12573/5>
