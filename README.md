# joppy

Python interface for the [Joplin data API](https://joplinapp.org/api/references/rest_api/).

## Installation

```bash
git clone https://github.com/marph91/joppy.git
cd joppy
pip install .
```

## Usage example

Start joplin and [get your API token](https://joplinapp.org/api/references/rest_api/#authorisation).

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

Now you can check joplin. There should be the note, contained by the notebook and decorated by the tag.

For more usage examples, check the [tests](test/test_api.py).

## Tests

To run the tests, some additional system packages and python modules are needed. After installing them, just run:

```bash
python -m unittest
```

It's possible to configure the test run via some environment variables:

* `SLOW_TESTS`: Set this variable to run the slow tests. Default not set.
* `API_TOKEN`: Set this variable if there is already a joplin instance running. **Don't use your default joplin profile!** By default, a joplin instance is started inside xvfb. This takes some time, but works for CI.

## FAQ

Short summary about questions I had during the implementation.

* What is the purpose/usecase of "user_created_time"? Isn't "created_time" sufficient? \rightarrow <https://discourse.joplinapp.org/t/importing-notes-from-tiddlywiki-api-feature-request-for-timestamps/1952/7>
* Why is the token in the query? \rightarrow <https://discourse.joplinapp.org/t/joplin-api-token-in-header-vs-query-parameters/12573/5>
