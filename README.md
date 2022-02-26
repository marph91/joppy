# joppy

Python interface for the [Joplin data API](https://joplinapp.org/api/references/rest_api/).

[![build](https://github.com/marph91/joppy/actions/workflows/build.yml/badge.svg)](https://github.com/marph91/joppy/actions/workflows/build.yml)
[![tests](https://github.com/marph91/joppy/actions/workflows/tests.yml/badge.svg)](https://github.com/marph91/joppy/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/marph91/joppy/branch/master/graph/badge.svg?token=97E6IX792A)](https://codecov.io/gh/marph91/joppy)
[![lint](https://github.com/marph91/joppy/actions/workflows/lint.yml/badge.svg)](https://github.com/marph91/joppy/actions/workflows/lint.yml)

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

Note: The API is tested with the latest release of Joplin on Ubuntu by github actions. It was reported that joppy is [working at windows 10](https://discourse.joplinapp.org/t/joplin-api-python/1359/39), too.

## :wrench: Usage

Start joplin and [get your API token](https://joplinapp.org/api/references/rest_api/#authorisation).

<details>
  <summary>Get all notes</summary>
  
  ```python
  from joppy.api import Api

  # Create a new Api instance.
  api = Api(token=YOUR_TOKEN)

  # Get all notes. Note that this method calls get_notes() multiple times to assemble the unpaginated result.
  notes = api.get_all_notes()
  ```
</details>

<details>
  <summary>Add a tag to a note</summary>
  
  ```python
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
  ```
</details>

<details>
  <summary>Add a resource to a note</summary>
  
  ```python
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
  ```
</details>

For more usage examples, check the example scripts or [tests](test/test_api.py).

## :newspaper: Example scripts

Before using joppy, you should check the [Joplin plugins](https://joplinapp.org/plugins/). They are probably more convenient. However, if you need a new feature or just want to code in python, you can use joppy. Below are example scripts to showcase how joppy can be used.

- [pdf_export.py](examples/pdf_export.py): Joplin only supports PDF export of a single note. This script allows to export one, multiple or all notebooks to PDF. Note that there are still some issues, like checkboxes don't get visualized correctly and big tables are truncated.

Scripts and projects from other users using joppy:
- https://github.com/gri38/django-joplin_vieweb: Web viewer for joplin.
- https://discourse.joplinapp.org/t/solved-tips-for-removing-safely-duplicated-notes-from-two-very-similar-notebooks/20943/9: Removing duplicated notes.
- https://discourse.joplinapp.org/t/joplin-api-python/1359/39: Not sure what it actually does :P

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
