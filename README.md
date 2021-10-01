# joppy

Python interface for the [Joplin data API](https://joplinapp.org/api/references/rest_api/).

## Installation

```bash
pip install joppy
```

## Usage example

Start joplin and [get your API token](https://joplinapp.org/api/references/rest_api/#authorisation).

```python
from joppy.api import Api

api = Api(token=YOUR_TOKEN)
notebook_id = api.add_notebook(title="My first notebook")
note_id = api.add_note(title="My first note", body="With some content", parent_id=notebook_id)
api.add_tag(title="introduction", parent_id=note_id)
```

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
