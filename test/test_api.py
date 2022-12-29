"""Tests for the joplin python API."""

from datetime import datetime
import itertools
import logging
import mimetypes
import os
import random
import re
import string
import tempfile
from typing import Any, Iterable, Mapping, Tuple
import unittest

import requests
import urllib3

from joppy import tools
from joppy.api import Api
import joppy.data_types as dt
from . import setup_joplin


os.makedirs("test_output", exist_ok=True)
logging.basicConfig(
    filename="test_output/test.log",
    filemode="w",
    format="%(asctime)s [%(levelname)s]: %(message)s",
    level=logging.DEBUG,
)


SLOW_TESTS = bool(os.getenv("SLOW_TESTS", ""))
PROFILE = "test_profile"
API_TOKEN = os.getenv("API_TOKEN", "")
APP = None


def with_resource(func):
    """Create a dummy resource and return it's filename."""

    def inner_decorator(self, *args, **kwargs):
        # TODO: Check why TemporaryFile() doesn't work.
        with tempfile.TemporaryDirectory() as tmpdirname:
            filename = f"{tmpdirname}/dummy.raw"
            open(filename, "w").close()

            return func(self, *args, **kwargs, filename=filename)

    return inner_decorator


def setUpModule():  # pylint: disable=invalid-name
    # TODO: When splitting in multiple files, this needs to be run at start of the
    # testsuite.
    global API_TOKEN, APP
    if not API_TOKEN:
        app_path = "./joplin.AppImage"
        setup_joplin.download_joplin(app_path)
        APP = setup_joplin.JoplinApp(app_path, profile=PROFILE)
        API_TOKEN = APP.api_token


def tearDownModule():  # pylint: disable=invalid-name
    if APP is not None:
        APP.stop()


class TestBase(unittest.TestCase):
    def setUp(self):
        super().setUp()

        logging.debug("Test: %s", self.id())

        self.api = Api(token=API_TOKEN)
        # Note: Notes get deleted automatically.
        self.api.delete_all_notebooks()
        self.api.delete_all_resources()
        self.api.delete_all_tags()

    @staticmethod
    def get_random_id() -> str:
        """Return a random, valid ID."""
        # https://stackoverflow.com/a/2782859/7410886
        return f"{random.randrange(16**32):032x}"

    @staticmethod
    def get_random_string(length: int = 8, exclude: str = "") -> str:
        """Return a random string."""
        characters = string.printable
        for character in exclude:
            characters = characters.replace(character, "")
        random_string = "".join(random.choice(characters) for _ in range(length))
        logging.debug("Test: random string: %s", random_string)
        return random_string

    @staticmethod
    def get_combinations(
        iterable: Iterable[str], max_combinations: int = 100
    ) -> Iterable[Tuple[str, ...]]:
        """Get some combinations of an iterable."""
        # https://stackoverflow.com/a/10465588
        # TODO: Randomize fully. For now the combinations are sorted by length.
        list_ = list(iterable)
        lengths = list(range(1, len(list_) + 1))
        random.shuffle(lengths)
        combinations = itertools.chain.from_iterable(
            itertools.combinations(list_, r)
            for r in lengths
            # shuffle each iteration
            if random.shuffle(list_) is None
        )
        return itertools.islice(combinations, max_combinations)


class Event(TestBase):
    def generate_event(self) -> None:
        """Generate an event and wait until it's available."""
        events = self.api.get_events()
        assert events.cursor is not None
        events_before = len(self.api.get_all_events(cursor=events.cursor))
        # For now only notes trigger events:
        # https://joplinapp.org/api/references/rest_api/#events
        self.api.add_notebook()
        self.api.add_note()

        def compare_event_count():
            assert events.cursor is not None
            event_count = len(self.api.get_all_events(cursor=events.cursor))
            return event_count if event_count == events_before + 1 else None

        # Wait until the event is available.
        setup_joplin.wait_for(compare_event_count, interval=0.1, timeout=1)

    def test_get_event(self):
        """Get a specific event."""
        events = self.api.get_events()
        assert events.cursor is not None
        self.generate_event()
        last_event = self.api.get_events(cursor=events.cursor).items[-1]
        assert last_event.id is not None
        event = self.api.get_event(id_=last_event.id)

        self.assertEqual(event.assigned_fields(), event.default_fields())
        self.assertEqual(event.type, dt.EventChangeType.CREATED)
        self.assertEqual(event.type_, dt.ItemType.ITEM_CHANGE)

        # TODO: What is the purpose?
        # for property_ in event.default_fields():
        #    # https://github.com/python/mypy/issues/7178
        #    self.assertEqual(event[property_], event[property_])  # type: ignore

    def test_get_events_by_cursor(self):
        """Get all events by specifying a cursor of 0."""
        previous_created_time = datetime(2000, 1, 1)
        previous_id = 0

        self.generate_event()
        events = self.api.get_events(cursor=0)

        for event in events.items:
            current_created_time = event.created_time
            assert current_created_time is not None
            assert event.id is not None
            self.assertGreater(current_created_time, previous_created_time)
            self.assertGreater(event.id, previous_id)
            previous_created_time = current_created_time
            previous_id = event.id
            self.assertEqual(event.assigned_fields(), event.default_fields())

    def test_get_events_empty(self):
        """
        If no cursor is given, the latest cursor is returned to retrieve future events.
        """
        events = self.api.get_events()
        self.assertEqual(events.items, [])
        self.assertFalse(events.has_more)

    def test_get_events_valid_properties(self):
        """Try to get specific properties of an event."""
        # TODO: Doesn't work with cursor=0
        property_combinations = self.get_combinations(dt.EventData.fields())
        for properties in property_combinations:
            events = self.api.get_events(fields=",".join(properties))
            for event in events.items:
                self.assertEqual(event.assigned_fields(), set(properties))


class Note(TestBase):
    def test_add(self):
        """Add a note to an existing notebook."""
        parent_id = self.api.add_notebook()
        id_ = self.api.add_note()

        notes = self.api.get_notes().items
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].id, id_)
        self.assertEqual(notes[0].parent_id, parent_id)

    def test_add_attach_image(self):
        """Add a note with an image attached."""
        self.api.add_notebook()
        image_data = tools.encode_base64("test/grant_authorization_button.png")
        note_id = self.api.add_note(
            image_data_url=f"data:image/png;base64,{image_data}"
        )

        # Check that there is a resource.
        resources = self.api.get_resources().items
        self.assertEqual(len(resources), 1)
        resource_id = resources[0].id

        # Verify the resource is attached to the note.
        resources = self.api.get_resources(note_id=note_id).items
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].id, resource_id)

    def test_add_no_notebook(self):
        """A note has to be added to an existing notebook."""
        with self.assertRaises(requests.exceptions.HTTPError) as context:
            self.api.add_note()
        self.assertEqual(context.exception.response.status_code, 500)
        self.assertIn(
            "Internal Server Error: Cannot find folder for note",
            context.exception.response.json()["error"],
        )

    def test_delete(self):
        """Add and then delete a note."""
        self.api.add_notebook()
        id_ = self.api.add_note()
        notes = self.api.get_notes()
        self.assertEqual(len(notes.items), 1)

        self.api.delete_note(id_=id_)
        self.assertEqual(self.api.get_notes().items, [])

    def test_get_note(self):
        """Get a specific note."""
        self.api.add_notebook()
        id_ = self.api.add_note()
        note = self.api.get_note(id_=id_)
        self.assertEqual(note.assigned_fields(), note.default_fields())
        self.assertEqual(note.type_, dt.ItemType.NOTE)

    def test_get_notes(self):
        """Get all notes."""
        self.api.add_notebook()
        self.api.add_note()
        notes = self.api.get_notes()
        self.assertEqual(len(notes.items), 1)
        self.assertFalse(notes.has_more)
        for note in notes.items:
            self.assertEqual(note.assigned_fields(), note.default_fields())

    def test_get_all_notes(self):
        """Get all notes, unpaginated."""
        self.api.add_notebook()
        # Small limit and count to create/remove as less as possible items.
        count, limit = random.randint(1, 10), random.randint(1, 10)
        for _ in range(count):
            self.api.add_note()
        self.assertEqual(len(self.api.get_notes(limit=limit).items), min(limit, count))
        self.assertEqual(len(self.api.get_all_notes(limit=limit)), count)

    def test_get_notes_too_many_ids(self):
        """At maximum one parent ID can be used to obtain notes."""
        with self.assertRaises(ValueError):
            self.api.get_notes(notebook_id="1", tag_id="2")

    def test_get_notes_valid_properties(self):
        """Try to get specific properties of a note."""
        self.api.add_notebook()
        self.api.add_note()
        # TODO: Some of the fields yield HTTP 500.
        selected_fields = dt.NoteData.fields() - {
            "body_html",
            "base_url",
            "image_data_url",
            "crop_rect",
        }
        property_combinations = self.get_combinations(selected_fields)
        for properties in property_combinations:
            notes = self.api.get_notes(fields=",".join(properties))
            for note in notes.items:
                self.assertEqual(note.assigned_fields(), set(properties))

    def test_move(self):
        """Move a note from one notebook to another."""
        original_title = "test title"
        original_body = "test body"

        notebook_1_id = self.api.add_notebook()
        notebook_2_id = self.api.add_notebook()
        id_ = self.api.add_note(
            parent_id=notebook_1_id, title=original_title, body=original_body
        )

        note = self.api.get_note(id_=id_)
        self.assertEqual(note.parent_id, notebook_1_id)

        self.api.modify_note(id_=id_, parent_id=notebook_2_id)
        note = self.api.get_note(id_=id_, fields="body,parent_id,title")
        self.assertEqual(note.parent_id, notebook_2_id)

        # Ensure the original properties aren't modified.
        self.assertEqual(note.body, original_body)
        self.assertEqual(note.title, original_title)


class Notebook(TestBase):
    def test_add(self):
        """Add a notebook."""
        id_ = self.api.add_notebook()

        notebooks = self.api.get_notebooks().items
        self.assertEqual(len(notebooks), 1)
        self.assertEqual(notebooks[0].id, id_)

    def test_get_notebook(self):
        """Get a specific notebook."""
        id_ = self.api.add_notebook()
        notebook = self.api.get_notebook(id_=id_)
        # TODO: properties instead of default_properties
        self.assertEqual(notebook.assigned_fields(), notebook.fields())
        self.assertEqual(notebook.type_, dt.ItemType.FOLDER)

    def test_get_notebooks(self):
        """Get all notebooks."""
        self.api.add_notebook()
        notebooks = self.api.get_notebooks()
        self.assertEqual(len(notebooks.items), 1)
        self.assertFalse(notebooks.has_more)
        for notebook in notebooks.items:
            self.assertEqual(notebook.assigned_fields(), notebook.default_fields())

    def test_get_all_notebooks(self):
        """Get all notebooks, unpaginated."""
        # Small limit and count to create/remove as less as possible items.
        count, limit = random.randint(1, 10), random.randint(1, 10)
        for _ in range(count):
            self.api.add_notebook()
        self.assertEqual(
            len(self.api.get_notebooks(limit=limit).items), min(limit, count)
        )
        self.assertEqual(len(self.api.get_all_notebooks(limit=limit)), count)

    def test_get_notebooks_invalid_property(self):
        """Try to get an non existent property of notebooks."""
        self.api.add_notebook()
        invalid_property = "invalid_property"
        with self.assertRaises(requests.exceptions.HTTPError) as context:
            self.api.get_notebooks(fields=invalid_property)
        self.assertEqual(context.exception.response.status_code, 500)
        self.assertIn(
            "Internal Server Error: Error: SQLITE_ERROR: no such column: "
            f"{invalid_property}",
            context.exception.response.json()["error"],
        )

    def test_get_notebooks_valid_properties(self):
        """Try to get specific properties of a notebook."""
        self.api.add_notebook()
        property_combinations = self.get_combinations(dt.NotebookData.fields())
        for properties in property_combinations:
            notebooks = self.api.get_notebooks(fields=",".join(properties))
            for notebook in notebooks.items:
                self.assertEqual(notebook.assigned_fields(), set(properties))

    def test_move(self):
        """Move a root notebok to another notebook. It's now a subnotebook."""
        first_id = self.api.add_notebook()
        second_id = self.api.add_notebook()
        self.assertEqual(self.api.get_notebook(id_=first_id).parent_id, "")
        self.assertEqual(self.api.get_notebook(id_=second_id).parent_id, "")

        self.api.modify_notebook(id_=first_id, parent_id=second_id)
        self.assertEqual(self.api.get_notebook(id_=first_id).parent_id, second_id)
        self.assertEqual(self.api.get_notebook(id_=second_id).parent_id, "")


class Ping(TestBase):
    def test_ping(self):
        """Ping should return the test string."""
        ping = self.api.ping()
        self.assertEqual(ping.text, "JoplinClipperServer")

    def test_ping_wrong_method(self):
        """Pinging the wrong method should return an error code."""
        for method in ("delete", "post", "put"):
            with self.subTest(method=method):
                with self.assertRaises(requests.exceptions.HTTPError) as context:
                    getattr(self.api, method)("/ping")
                self.assertEqual(context.exception.response.status_code, 405)


class Resource(TestBase):
    @with_resource
    def test_add(self, filename):
        """Add a resource."""
        id_ = self.api.add_resource(filename=filename)

        resources = self.api.get_resources().items
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].id, id_)

    @with_resource
    def test_add_to_note(self, filename):
        """Add a resource to an existing note."""
        self.api.add_notebook()
        note_id = self.api.add_note()
        resource_id = self.api.add_resource(filename=filename)
        self.api.add_resource_to_note(resource_id=resource_id, note_id=note_id)

        # Verify the resource is attached to the note.
        resources = self.api.get_resources(note_id=note_id).items
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].id, resource_id)

        # TODO: Seems to be not working.
        # notes = self.api.get_notes(resource_id=resource_id)["items"]
        # self.assertEqual(len(notes), 1)
        # self.assertEqual(notes[0]["id"], note_id)

    @with_resource
    def test_delete(self, filename):
        """Add and then delete a resource."""
        id_ = self.api.add_resource(filename=filename)
        resources = self.api.get_resources()
        self.assertEqual(len(resources.items), 1)

        self.api.delete_resource(id_=id_)
        self.assertEqual(self.api.get_resources().items, [])
        self.assertEqual(os.listdir(f"{PROFILE}/resources"), [])

    @with_resource
    def test_get_resource(self, filename):
        """Get metadata about a specific resource."""
        id_ = self.api.add_resource(filename=filename)
        resource = self.api.get_resource(id_=id_)
        self.assertEqual(resource.assigned_fields(), resource.default_fields())
        self.assertEqual(resource.type_, dt.ItemType.RESOURCE)

    @with_resource
    def test_get_resource_file(self, filename):
        """Get a specific resource in binary format."""
        for file_ in ("test/grant_authorization_button.png", filename):
            id_ = self.api.add_resource(filename=file_)
            resource = self.api.get_resource_file(id_=id_)
            with open(file_, "rb") as resource_file:
                self.assertEqual(resource, resource_file.read())

    @with_resource
    def test_get_resources(self, filename):
        """Get all resources."""
        self.api.add_resource(filename=filename)
        resources = self.api.get_resources()
        self.assertEqual(len(resources.items), 1)
        self.assertFalse(resources.has_more)
        for resource in resources.items:
            self.assertEqual(resource.assigned_fields(), resource.default_fields())

    @with_resource
    def test_get_all_resources(self, filename):
        """Get all resources, unpaginated."""
        # Small limit and count to create/remove as less as possible items.
        count, limit = random.randint(1, 10), random.randint(1, 10)
        for _ in range(count):
            self.api.add_resource(filename=filename)
        self.assertEqual(
            len(self.api.get_resources(limit=limit).items), min(limit, count)
        )
        self.assertEqual(len(self.api.get_all_resources(limit=limit)), count)

    @with_resource
    def test_get_resources_valid_properties(self, filename):
        """Try to get specific properties of a resource."""
        self.api.add_resource(filename=filename)
        property_combinations = self.get_combinations(dt.ResourceData.fields())
        for properties in property_combinations:
            resources = self.api.get_resources(fields=",".join(properties))
            for resource in resources.items:
                self.assertEqual(resource.assigned_fields(), set(properties))

    @with_resource
    def test_modify_title(self, filename):
        """Modify a resource title."""
        id_ = self.api.add_resource(filename=filename)

        new_title = self.get_random_string()
        self.api.modify_resource(id_=id_, title=new_title)
        self.assertEqual(self.api.get_resource(id_=id_).title, new_title)

    @with_resource
    def test_check_derived_properties(self, filename):
        """Check the derived properties. I. e. mime type, extension and size."""
        for file_ in ["test/grant_authorization_button.png", filename]:
            id_ = self.api.add_resource(filename=file_)
            resource = self.api.get_resource(id_=id_, fields="mime,file_extension,size")
            mime_type, _ = mimetypes.guess_type(file_)
            self.assertEqual(
                resource.mime,
                mime_type if mime_type is not None else "application/octet-stream",
            )
            self.assertEqual(resource.file_extension, os.path.splitext(file_)[1][1:])
            self.assertEqual(resource.size, os.path.getsize(file_))

    @with_resource
    def test_check_property_title(self, filename):
        """Check the title of a resource."""
        title = self.get_random_string()
        id_ = self.api.add_resource(filename=filename, title=title)
        resource = self.api.get_resource(id_=id_)
        self.assertEqual(resource.title, title)


# TODO: Add more tests for the search parameter.
class Search(TestBase):
    def test_empty(self):
        """Search should succeed, even if there is no result item."""
        self.assertEqual(self.api.search(query="*").items, [])

    def test_notes(self):
        """
        Wildcard search for all notes is disabled, because of performance reasons.
        See: https://github.com/laurent22/joplin/issues/5546
        """
        self.api.add_notebook()
        self.api.add_note()
        self.assertEqual(self.api.search(query="*").items, [])
        self.assertEqual(self.api.search(query="*", type="note").items, [])

    def test_notebooks(self):
        """Search by notebooks and search endpoint should yield same results."""
        self.api.add_notebook()
        self.assertEqual(
            self.api.search(query="*", type="folder"),
            self.api.get_notebooks(),
        )

    @with_resource
    def test_resources(self, filename):
        """Search by resources and search endpoint should yield same results."""
        self.api.add_resource(filename=filename)
        self.assertEqual(
            self.api.search(query="*", type="resource"),
            self.api.get_resources(),
        )

    def test_tags(self):
        """Search by tags and search endpoint should yield same results."""
        self.api.add_tag()
        self.assertEqual(
            self.api.search(query="*", type="tag"),
            self.api.get_tags(),
        )

    def test_master_key(self):
        """There is no master key configured."""
        self.assertEqual(
            self.api.search(query="*", type="master_key").items,
            [],
        )

    def test_non_searchable(self):
        """Check if the non searchable types throw an error."""
        # fmt: off
        for type_ in ("setting", "note_tag", "search", "alarm", "item_change",
                      "note_resource", "resource_local_state", "revision", "migration",
                      "smart_filter", "command"):
            with self.assertRaises(requests.exceptions.HTTPError) as context:
                self.api.search(query="*", type=type_)
            self.assertEqual(context.exception.response.status_code, 500)
        # fmt: on

    def test_pagination(self):
        """If there are more than 10 items, the results will be paginated."""
        limit = 10  # maximum 100

        for _ in range(limit + 1):
            self.api.add_notebook()

        query: dt.JoplinKwargs = {"query": "*", "type": "folder", "limit": limit}
        search_result = self.api.search(**query)
        self.assertEqual(len(search_result.items), limit)
        self.assertTrue(search_result.has_more)

        query["page"] = 2
        search_result = self.api.search(**query)
        self.assertEqual(len(search_result.items), 1)
        self.assertFalse(search_result.has_more)

    def test_search_query_special_chars(self):
        """
        Search should succeed even with special characters.
        See: https://github.com/marph91/joppy/issues/5
        """
        queries = (
            (
                "https://books.google.com.br/books?id=vaZFBgAAQBAJ&pg=PA83&dq=lakatos+"
                "copernicus&hl=pt-BR&sa=X&ved=0ahUKEwjewoWZ6q7hAhUNJ7kGHdy5CZUQ6AEIUDA"
                r"F#v=onepage&q=lakatos%20copernicus&f=false"
            ),
            (
                "https://www.facebook.com/photo.php?fbid=621934757910715&set=a.1437947"
                "52391387&type=3&app=fbl"
            ),
            r"foo# ?bar%+!baz",
            # Leading slashes in notebooks are stripped by default:
            # https://github.com/laurent22/joplin/issues/6213
            self.get_random_string().lstrip("/\\"),
        )

        for query in queries:
            self.api.add_notebook(title=query)
            result = self.api.search(query=query, type="folder")
            self.assertEqual(len(result.items), 1)
            self.assertEqual(result.items[0].title, query)

    def test_search_all(self):
        """Search notebooks and return all results, unpaginated."""
        # Small limit and count to create/remove as less as possible items.
        count, limit = random.randint(1, 10), random.randint(1, 10)
        # Leading slashes in notebooks are stripped by default:
        # https://github.com/laurent22/joplin/issues/6213
        title = self.get_random_string().lstrip("/\\")
        query: dt.JoplinKwargs = {"query": title, "type": "folder", "limit": limit}
        for _ in range(count):
            self.api.add_notebook(title=title)
        self.assertEqual(len(self.api.search(**query).items), min(limit, count))
        self.assertEqual(len(self.api.search_all(**query)), count)


class Tag(TestBase):
    def test_add_no_note(self):
        """Tags can be added even without notes."""
        id_ = self.api.add_tag()

        tags = self.api.get_tags().items
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0].id, id_)

    def test_add_to_note(self):
        """Add a tag to an existing note."""
        self.api.add_notebook()
        note_id = self.api.add_note()
        tag_id = self.api.add_tag()
        self.api.add_tag_to_note(tag_id=tag_id, note_id=note_id)

        notes = self.api.get_notes(tag_id=tag_id).items
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].id, note_id)
        tags = self.api.get_all_tags()
        self.assertEqual(len(tags), 1)

    def test_add_with_parent(self):
        """Add a tag as child for an existing note."""
        self.api.add_notebook()
        parent_id = self.api.add_note()
        id_ = self.api.add_tag(parent_id=parent_id)

        tags = self.api.get_tags().items
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0].id, id_)
        self.assertEqual(tags[0].parent_id, parent_id)

    def test_add_duplicated_name(self):
        """Tag names have to be unique."""
        # Note: Tags are always lower case:
        # https://discourse.joplinapp.org/t/tags-lower-case-only/4220
        # Note: Whitespace chars are substituted.
        tag_name = self.get_random_string(exclude=string.whitespace)

        self.api.add_tag(title=tag_name)
        with self.assertRaises(requests.exceptions.HTTPError) as context:
            self.api.add_tag(title=tag_name)
        self.assertEqual(context.exception.response.status_code, 500)
        self.assertIn(
            f'Internal Server Error: The tag "{tag_name.lower()}" already exists',
            context.exception.response.json()["error"],
        )

    def test_add_duplicated_id(self):
        """Tag IDs have to be unique."""
        tag_id = self.get_random_id()

        self.api.add_tag(id_=tag_id)
        with self.assertRaises(requests.exceptions.HTTPError) as context:
            self.api.add_tag(id_=tag_id)
        self.assertEqual(context.exception.response.status_code, 500)
        self.assertIn(
            "Internal Server Error: Error: SQLITE_CONSTRAINT: UNIQUE constraint failed",
            context.exception.response.json()["error"],
        )

    def test_get_tag(self):
        """Get a specific tag."""
        id_ = self.api.add_tag()
        tag = self.api.get_tag(id_=id_)
        self.assertEqual(tag.assigned_fields(), tag.default_fields())
        self.assertEqual(tag.type_, dt.ItemType.TAG)

    def test_get_tags(self):
        """Get all tags."""
        self.api.add_tag()
        tags = self.api.get_tags()
        self.assertEqual(len(tags.items), 1)
        self.assertFalse(tags.has_more)
        for tag in tags.items:
            self.assertEqual(tag.assigned_fields(), tag.default_fields())

    def test_get_all_tags(self):
        """Get all tags, unpaginated."""
        # Small limit and count to create/remove as less as possible items.
        count, limit = random.randint(1, 10), random.randint(1, 10)
        for _ in range(count):
            self.api.add_tag()
        self.assertEqual(len(self.api.get_tags(limit=limit).items), min(limit, count))
        self.assertEqual(len(self.api.get_all_tags(limit=limit)), count)

    def test_get_tags_valid_properties(self):
        """Try to get specific properties of a tag."""
        self.api.add_tag()
        property_combinations = self.get_combinations(dt.TagData.fields())
        for properties in property_combinations:
            tags = self.api.get_tags(fields=",".join(properties))
            for tag in tags.items:
                self.assertEqual(tag.assigned_fields(), set(properties))


class Fuzz(TestBase):
    def test_random_path(self):
        """API should not crash, even with invalid paths."""
        for _ in range(1000 if SLOW_TESTS else 10):
            path = "/" + self.get_random_string(length=random.randint(0, 300))
            method = random.choice(("delete", "get", "post", "put"))
            try:
                self.api._request(method, path)
            except (
                requests.exceptions.HTTPError,
                urllib3.exceptions.LocationParseError,
            ):
                pass
        self.api.ping()


class Helper(TestBase):
    """Tests for the helper functions."""

    def test_random_id(self):
        """Random IDs should always be valid."""
        for _ in range(100):
            self.assertTrue(dt.is_id_valid(self.get_random_id()))

    def test_is_id_valid(self):
        """Trivial test for the is_id_valid() function."""
        self.assertTrue(dt.is_id_valid("0" * 32))

        # ID has to be 32 chars.
        self.assertFalse(dt.is_id_valid("0" * 31))

        # ID has to be contain only hex chars.
        self.assertFalse(dt.is_id_valid("h" + "0" * 31))


class Miscellaneous(TestBase):
    @with_resource
    def test_same_id_different_type(self, filename):
        """Same IDs can be used if the types are different."""
        id_ = self.get_random_id()

        self.api.add_notebook(id_=id_)
        self.api.add_note(id_=id_)
        self.api.add_resource(id_=id_, filename=filename)
        self.api.add_tag(id_=id_)


class Regression(TestBase):
    @unittest.skip("Enable when the bug is fixed.")
    @unittest.skipIf(not SLOW_TESTS, "Generating the long string is slow.")
    def test_long_body(self):
        """
        https://github.com/laurent22/joplin/issues/5543
        Response HTTP 104: https://stackoverflow.com/a/52826181
        """
        # Use only one random character, since it's very slow already.
        body = self.get_random_string(1) * 10**9
        self.api.add_notebook()
        note_id = self.api.add_note(body=body)
        self.assertEqual(self.api.get_note(id_=note_id).title, body)

    def test_note_tag_fields(self):
        """https://github.com/laurent22/joplin/issues/4407"""
        self.api.add_notebook()
        note_id = self.api.add_note()
        tag_id = self.api.add_tag()
        self.api.add_tag_to_note(tag_id=tag_id, note_id=note_id)

        notes = self.api.get_notes(tag_id=tag_id, fields="id")
        self.assertEqual(notes.items[0].assigned_fields(), {"id"})

    @unittest.skip("Not yet implemented")
    def test_set_location(self):
        """https://github.com/laurent22/joplin/issues/3884"""

    @unittest.skip("Not yet implemented")
    def test_add_todo(self):
        """https://github.com/laurent22/joplin/issues/1687"""


class ReadmeExamples(TestBase):
    """Check the readme examples for functionality."""

    readme_content: str = ""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        with open("README.md", encoding="utf-8") as infile:
            readme_content = infile.read()

        # Replace the token to make the code functional.
        cls.readme_content = readme_content.replace("YOUR_TOKEN", f'"{API_TOKEN}"')

    def get_example_code(self, example_name: str) -> str:
        """
        Get the code of a readme example by its name.
        The example can be identified by a custom info string in markdown.
        See: https://spec.commonmark.org/0.30/#example-143
        """

        matches = re.search(
            f"```python name={example_name}\n(.*?)```",
            self.readme_content,
            flags=re.DOTALL,
        )
        # TODO: Use "assertIsNotNone()" when
        # https://github.com/python/mypy/issues/5528 is resolved.
        assert matches is not None
        self.assertEqual(len(matches.groups()), 1)
        return matches.groups()[0]

    def test_get_all_notes(self):

        note_count = 3
        self.api.add_notebook()
        for _ in range(note_count):
            self.api.add_note()

        # Execute the example code. The local variables are stored in "locals_dict".
        code = self.get_example_code("get_all_notes")
        locals_dict: Mapping[str, Any] = {}
        exec(code, None, locals_dict)

        self.assertEqual(len(locals_dict["notes"]), note_count)

    def test_add_tag_to_note(self):

        code = self.get_example_code("add_tag_to_note")
        exec(code)

        tags = self.api.get_all_tags()
        self.assertEqual(len(tags), 1)

        assert tags[0].id is not None
        notes = self.api.get_all_notes(tag_id=tags[0].id)
        self.assertEqual(len(notes), 1)

    def test_add_resource_to_note(self):

        code = self.get_example_code("add_resource_to_note")
        code = code.replace("path/to/image.png", "test/grant_authorization_button.png")
        exec(code)

        notes = self.api.get_all_notes()
        self.assertEqual(len(notes), 2)

        resources = self.api.get_all_resources()
        self.assertEqual(len(resources), 2)

        # Each note should reference to exactly one resource.
        for note in notes:
            assert note.id is not None
            resources = self.api.get_all_resources(note_id=note.id)
            self.assertEqual(len(resources), 1)

    def test_remove_tags(self):

        self.api.add_tag(title="Title")
        self.api.add_tag(title="! Another Title")
        self.api.add_tag(title="!_third_title")

        code = self.get_example_code("remove_tags")
        exec(code)

        # All tags starting with "!" should be removed.
        tags = self.api.get_all_tags()
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0].title, "title")  # tags are always lower case

    def test_remove_spaces_from_tags(self):

        self.api.add_tag(title="tag with spaces")
        self.api.add_tag(title="another tag with spaces")

        code = self.get_example_code("remove_spaces_from_tags")
        exec(code)

        all_tags = self.api.get_all_tags()
        self.assertEqual(len(all_tags), 2)
        for tag in all_tags:
            assert tag.title is not None
            self.assertNotIn(" ", tag.title)

    @with_resource
    def test_remove_orphaned_resources(self, filename):

        self.api.add_notebook()
        for i in range(2):
            note_id = self.api.add_note()
            resource_id = self.api.add_resource(
                filename=filename, title=f"resource {i}"
            )
            self.api.add_resource_to_note(resource_id=resource_id, note_id=note_id)

        # Delete the second note, which creates an orphaned resource.
        self.api.delete_note(note_id)
        self.assertEqual(len(self.api.get_all_resources()), 2)

        code = self.get_example_code("remove_orphaned_resources")
        exec(code)

        # The resource without reference should be deleted.
        resources = self.api.get_all_resources()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].title, "resource 0")
