"""Tests for the joplin python API."""

import enum
import itertools
import logging
import os
import random
from re import sub
import string
import tempfile
import time
import unittest

from parameterized import parameterized
import requests

from joppy.api import Api
from . import setup_joplin


logging.basicConfig(
    filename="test.log",
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


class ChangeType(enum.Enum):
    # https://joplinapp.org/api/references/rest_api/#properties-4
    CREATED = 1
    UPDATED = 2
    DELETED = 3


class ItemType(enum.Enum):
    # https://joplinapp.org/api/references/rest_api/#item-type-ids
    NOTE = 1
    FOLDER = 2
    SETTING = 3
    RESOURCE = 4
    TAG = 5
    NOTE_TAG = 6
    SEARCH = 7
    ALARM = 8
    MASTER_KEY = 9
    ITEM_CHANGE = 10
    NOTE_RESOURCE = 11
    RESOURCE_LOCAL_STATE = 12
    REVISION = 13
    MIGRATION = 14
    SMART_FILTER = 15
    COMMAND = 16


def setUpModule():
    # TODO: When splitting in multiple files, this needs to be run at start of the
    # testsuite.
    global API_TOKEN, APP
    if not API_TOKEN:
        app_path = "./joplin.AppImage"
        setup_joplin.download_joplin(app_path)
        APP = setup_joplin.JoplinApp(app_path, profile=PROFILE)
        API_TOKEN = APP.api_token


def tearDownModule():
    if APP is not None:
        APP.stop()


class TestBase(unittest.TestCase):
    empty_search = {"items": [], "has_more": False}

    def setUp(self):
        super().setUp()
        self.api = Api(token=API_TOKEN)
        # Note: Notes get deleted automatically.
        self.api.delete_all_notebooks()
        self.api.delete_all_resources()
        self.api.delete_all_tags()
        self.current_cursor = self.api.get_events()["cursor"]

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
        return "".join(random.choice(characters) for _ in range(length))

    @staticmethod
    def is_id_valid(id_: str) -> bool:
        """
        Check whether a string is a valid id. See:
        https://joplinapp.org/api/references/rest_api/#creating-a-note-with-a-specific-id.
        """
        if len(id_) != 32:
            return False
        # https://stackoverflow.com/a/11592279/7410886
        try:
            int(id_, 16)
        except ValueError:
            return False
        return True

    @staticmethod
    def is_timestamp_valid(timestamp: int) -> bool:
        """Check whether a timestamp is valid."""
        # https://joplinapp.org/api/references/rest_api/#about-the-property-types
        return 0 <= timestamp <= int(time.time() * 1000)  # ms

    @staticmethod
    def get_combinations(iterable, max_combinations: int = 100):
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
            if random.shuffle(list_) is None  # type: ignore
        )
        return itertools.islice(combinations, max_combinations)


class Event(TestBase):
    properties = [
        # fmt: off
        "id", "item_type", "item_id", "type", "created_time",
        # "source", "before_change_item",
        # fmt: on
    ]
    default_properties = ["id", "item_type", "item_id", "type", "created_time"]

    def generate_event(self):
        """Generate an event and wait until it's available."""
        events_before = len(self.api.get_all_events(cursor=self.current_cursor))
        # For now only notes trigger events:
        # https://joplinapp.org/api/references/rest_api/#events
        self.api.add_notebook()
        self.api.add_note()

        def compare_event_count():
            event_count = len(self.api.get_all_events(cursor=self.current_cursor))
            return event_count if event_count == events_before + 1 else None

        # Wait until the event is available.
        setup_joplin.wait_for(compare_event_count, interval=0.1, timeout=1)

    def test_get_event(self):
        """Get a specific event."""
        self.generate_event()
        last_event = self.api.get_events(cursor=self.current_cursor)["items"][-1]
        event = self.api.get_event(id_=last_event["id"])

        self.assertEqual(list(event.keys()), self.default_properties + ["type_"])
        self.assertIn(event["item_type"], ItemType._value2member_map_)
        self.assertTrue(self.is_id_valid(event["item_id"]))
        self.assertEqual(event["type"], ChangeType.CREATED.value)
        self.assertTrue(self.is_timestamp_valid(event["created_time"]))
        self.assertEqual(event["type_"], ItemType.ITEM_CHANGE.value)

        for property_ in self.default_properties:
            self.assertEqual(event[property_], event[property_])

    def test_get_events_by_cursor(self):
        """Get all events by specifying a cursor of 0."""
        self.generate_event()
        events = self.api.get_events(cursor=0)

        previous_created_time = 0
        previous_id = 0
        for event in events["items"]:
            self.assertGreater(event["created_time"], previous_created_time)
            self.assertGreater(event["id"], previous_id)
            previous_created_time = event["created_time"]
            previous_id = event["id"]
            self.assertEqual(list(event.keys()), self.default_properties)

    def test_get_events_empty(self):
        """
        If no cursor is given, the latest cursor is returned to retrieve future events.
        """
        events = self.api.get_events()
        self.assertEqual(events["items"], [])
        self.assertFalse(events["has_more"])
        self.assertIn("cursor", events)

    def test_get_events_valid_properties(self):
        """Try to get specific properties of an event."""
        # TODO: Doesn't work with cursor=0
        property_combinations = self.get_combinations(self.properties)
        for properties in property_combinations:
            events = self.api.get_events(fields=",".join(properties))
            for event in events["items"]:
                self.assertEqual(list(event.keys()), list(properties))


class Note(TestBase):
    properties = [
        # fmt: off
        "id", "parent_id", "title", "body", "created_time", "updated_time",
        "is_conflict", "latitude", "longitude", "altitude", "author", "source_url",
        "is_todo", "todo_due", "todo_completed", "source", "source_application",
        "application_data", "order", "user_created_time", "user_updated_time",
        "encryption_cipher_text", "encryption_applied", "markup_language",
        "is_shared", "share_id", "conflict_original_id",
        # "body_html", "base_url", "image_data_url", "crop_rect",
        # fmt: on
    ]
    default_properties = ["id", "parent_id", "title"]

    def test_add(self):
        """Add a note to an existing notebook."""
        parent_id = self.api.add_notebook()
        id_ = self.api.add_note()

        self.assertTrue(self.is_id_valid(parent_id))
        self.assertTrue(self.is_id_valid(id_))

        notes = self.api.get_notes()["items"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["id"], id_)
        self.assertEqual(notes[0]["parent_id"], parent_id)

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
        self.assertEqual(len(notes["items"]), 1)

        self.api.delete_note(id_=id_)
        self.assertEqual(self.api.get_notes(), self.empty_search)

    def test_get_note(self):
        """Get a specific note."""
        self.api.add_notebook()
        id_ = self.api.add_note()
        note = self.api.get_note(id_=id_)
        self.assertEqual(list(note.keys()), self.default_properties + ["type_"])
        self.assertEqual(note["type_"], ItemType.NOTE.value)

    def test_get_notes(self):
        """Get all notes."""
        self.api.add_notebook()
        self.api.add_note()
        notes = self.api.get_notes()
        self.assertEqual(len(notes["items"]), 1)
        self.assertFalse(notes["has_more"])
        for note in notes["items"]:
            self.assertEqual(list(note.keys()), self.default_properties)

    def test_get_notes_too_many_ids(self):
        """At maximum one parent ID can be used to obtain notes."""
        with self.assertRaises(ValueError):
            self.api.get_notes(notebook_id="1", tag_id="2")

    def test_get_notes_valid_properties(self):
        """Try to get specific properties of a note."""
        self.api.add_notebook()
        self.api.add_note()
        property_combinations = self.get_combinations(self.properties)
        for properties in property_combinations:
            notes = self.api.get_notes(fields=",".join(properties))
            for note in notes["items"]:
                self.assertEqual(list(note.keys()), list(properties))

    def test_move(self):
        """Move a note from one notebook to another."""
        notebook_1_id = self.api.add_notebook()
        notebook_2_id = self.api.add_notebook()
        id_ = self.api.add_note(parent_id=notebook_1_id)

        note = self.api.get_note(id_=id_)
        self.assertEqual(note["parent_id"], notebook_1_id)

        self.api.modify_note(id_=id_, parent_id=notebook_2_id)
        note = self.api.get_note(id_=id_)
        self.assertEqual(note["parent_id"], notebook_2_id)


class Notebook(TestBase):
    properties = [
        # fmt: off
        "id", "title", "created_time", "updated_time",
        "user_created_time", "user_updated_time", "encryption_cipher_text",
        "encryption_applied", "parent_id", "is_shared", "share_id",
        # fmt: on
    ]
    default_properties = ["id", "parent_id", "title"]

    def test_add(self):
        """Add a notebook."""
        id_ = self.api.add_notebook()

        self.assertTrue(self.is_id_valid(id_))

        notebooks = self.api.get_notebooks()["items"]
        self.assertEqual(len(notebooks), 1)
        self.assertEqual(notebooks[0]["id"], id_)

    def test_get_notebook(self):
        """Get a specific notebook."""
        id_ = self.api.add_notebook()
        notebook = self.api.get_notebook(id_=id_)
        # TODO: properties instead of default_properties
        self.assertEqual(list(notebook.keys()), self.properties + ["type_"])
        self.assertEqual(notebook["type_"], ItemType.FOLDER.value)

    def test_get_notebooks(self):
        """Get all notebooks."""
        self.api.add_notebook()
        notebooks = self.api.get_notebooks()
        self.assertEqual(len(notebooks["items"]), 1)
        self.assertFalse(notebooks["has_more"])
        for notebook in notebooks["items"]:
            self.assertEqual(list(notebook.keys()), self.default_properties)

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
        property_combinations = self.get_combinations(self.properties)
        for properties in property_combinations:
            notebooks = self.api.get_notebooks(fields=",".join(properties))
            for notebook in notebooks["items"]:
                self.assertEqual(list(notebook.keys()), list(properties))

    def test_move(self):
        """Move a root notebok to another notebook. It's now a subnotebook."""
        first_id = self.api.add_notebook()
        second_id = self.api.add_notebook()
        self.assertEqual(self.api.get_notebook(id_=first_id)["parent_id"], "")
        self.assertEqual(self.api.get_notebook(id_=second_id)["parent_id"], "")

        self.api.modify_notebook(id_=first_id, parent_id=second_id)
        self.assertEqual(self.api.get_notebook(id_=first_id)["parent_id"], second_id)
        self.assertEqual(self.api.get_notebook(id_=second_id)["parent_id"], "")


class Ping(TestBase):
    def test_ping(self):
        """Ping should return the test string."""
        ping = self.api.ping()
        self.assertEqual(ping.text, "JoplinClipperServer")

    @parameterized.expand(("delete", "post", "put"))
    def test_ping_wrong_method(self, method):
        """Pinging the wrong method should return an error code."""
        with self.assertRaises(requests.exceptions.HTTPError) as context:
            getattr(self.api, method)("/ping")
        self.assertEqual(context.exception.response.status_code, 405)


class Resource(TestBase):
    properties = [
        # fmt: off
        "id", "title", "mime", "filename", "created_time", "updated_time",
        "user_created_time", "user_updated_time", "file_extension",
        "encryption_cipher_text", "encryption_applied", "encryption_blob_encrypted",
        "size", "is_shared", "share_id",
        # fmt: on
    ]
    default_properties = ["id", "title"]

    @with_resource
    def test_add(self, filename: str):
        """Add a resource."""
        id_ = self.api.add_resource(filename=filename)
        self.assertTrue(self.is_id_valid(id_))

        resources = self.api.get_resources()["items"]
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]["id"], id_)

    @with_resource
    def test_delete(self, filename: str):
        """Add and then delete a resource."""
        id_ = self.api.add_resource(filename=filename)
        resources = self.api.get_resources()
        self.assertEqual(len(resources["items"]), 1)

        self.api.delete_resource(id_=id_)
        self.assertEqual(self.api.get_resources(), self.empty_search)
        self.assertEqual(os.listdir(f"{PROFILE}/resources"), [])

    @with_resource
    def test_get_resource(self, filename):
        """Get a specific resource."""
        id_ = self.api.add_resource(filename=filename)
        resource = self.api.get_resource(id_=id_)
        self.assertEqual(list(resource.keys()), self.default_properties + ["type_"])
        self.assertEqual(resource["type_"], ItemType.RESOURCE.value)

    @with_resource
    def test_get_resources(self, filename):
        """Get all resources."""
        self.api.add_resource(filename=filename)
        resources = self.api.get_resources()
        self.assertEqual(len(resources["items"]), 1)
        self.assertFalse(resources["has_more"])
        for resource in resources["items"]:
            self.assertEqual(list(resource.keys()), self.default_properties)

    @with_resource
    def test_get_resources_valid_properties(self, filename):
        """Try to get specific properties of a resource."""
        self.api.add_resource(filename=filename)
        property_combinations = self.get_combinations(self.properties)
        for properties in property_combinations:
            resources = self.api.get_resources(fields=",".join(properties))
            for resource in resources["items"]:
                self.assertEqual(list(resource.keys()), list(properties))

    @with_resource
    def test_modify_title(self, filename: str):
        """Modify a resource title."""
        id_ = self.api.add_resource(filename=filename)

        new_title = self.get_random_string()
        self.api.modify_resource(id_=id_, title=new_title)
        self.assertEqual(self.api.get_resource(id_=id_)["title"], new_title)

    @with_resource
    def test_check_property_size(self, filename):
        """Check the size of a resource."""
        for file_ in ["test/grant_authorization_button.png", filename]:
            id_ = self.api.add_resource(filename=file_)
            resource = self.api.get_resource(id_=id_, fields="size")
            self.assertEqual(resource["size"], os.path.getsize(file_))

    @with_resource
    def test_check_property_extension(self, filename):
        """Check the extension of a resource."""
        for file_ in ["test/grant_authorization_button.png", filename]:
            id_ = self.api.add_resource(filename=file_)
            resource = self.api.get_resource(id_=id_, fields="file_extension")
            self.assertEqual(resource["file_extension"], os.path.splitext(file_)[1][1:])


# TODO: Add more tests for the search parameter.
class Search(TestBase):
    def test_empty(self):
        """Search should succeed, even if there is no result item."""
        self.assertEqual(self.api.search(query="*"), self.empty_search)

    def test_notes(self):
        """
        Wildcard search for all notes is disabled, because of performance reasons.
        See: https://github.com/laurent22/joplin/issues/5546
        """
        self.api.add_notebook()
        self.api.add_note()
        self.assertEqual(self.api.search(query="*"), self.empty_search)
        self.assertEqual(self.api.search(query="*", type="note"), self.empty_search)

    def test_notebooks(self):
        """Search by notebooks and search endpoint should yield same results."""
        self.api.add_notebook()
        self.assertEqual(
            self.api.search(query="*", type="folder"),
            self.api.get_notebooks(),
        )

    def test_sub_notebooks(self):
        """Search for all notebooks, contained by a specific notebook."""
        self.skipTest("TODO: Not possible yet?")

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
            self.api.search(query={"query": "*", "type": "master_key"}),
            self.empty_search,
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

        query = {"query": "*", "type": "folder", "limit": limit}
        search_result = self.api.search(**query)
        self.assertEqual(len(search_result["items"]), limit)
        self.assertTrue(search_result["has_more"])

        query["page"] = 2
        search_result = self.api.search(**query)
        self.assertEqual(len(search_result["items"]), 1)
        self.assertFalse(search_result["has_more"])


class Tag(TestBase):
    properties = [
        # fmt: off
        "id", "parent_id", "title", "created_time", "updated_time",
        "user_created_time", "user_updated_time", "encryption_cipher_text",
        "encryption_applied", "is_shared",
        # fmt: on
    ]
    default_properties = ["id", "parent_id", "title"]

    def test_add_no_note(self):
        """Tags can be added even without notes."""
        id_ = self.api.add_tag()

        tags = self.api.get_tags()["items"]
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0]["id"], id_)

    def test_add_to_note(self):
        """Add a tag to an existing note."""
        self.api.add_notebook()
        note_id = self.api.add_note()
        tag_id = self.api.add_tag()
        self.api.add_tag_to_note(tag_id=tag_id, note_id=note_id)

        notes = self.api.get_notes(tag_id=tag_id)["items"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["id"], note_id)

    def test_add_with_parent(self):
        """Add a tag as child for an existing note."""
        self.api.add_notebook()
        parent_id = self.api.add_note()
        id_ = self.api.add_tag(parent_id=parent_id)

        self.assertTrue(self.is_id_valid(parent_id))
        self.assertTrue(self.is_id_valid(id_))

        tags = self.api.get_tags()["items"]
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0]["id"], id_)
        self.assertEqual(tags[0]["parent_id"], parent_id)

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
        self.assertEqual(list(tag.keys()), self.default_properties + ["type_"])
        self.assertEqual(tag["type_"], ItemType.TAG.value)

    def test_get_tags(self):
        """Get all tags."""
        self.api.add_tag()
        tags = self.api.get_tags()
        self.assertEqual(len(tags["items"]), 1)
        self.assertFalse(tags["has_more"])
        for tag in tags["items"]:
            self.assertEqual(list(tag.keys()), self.default_properties)

    def test_get_tags_valid_properties(self):
        """Try to get specific properties of a tag."""
        self.api.add_tag()
        property_combinations = self.get_combinations(self.properties)
        for properties in property_combinations:
            tags = self.api.get_tags(fields=",".join(properties))
            for tag in tags["items"]:
                self.assertEqual(list(tag.keys()), list(properties))


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
                requests.packages.urllib3.exceptions.LocationParseError,
            ):
                pass
        self.api.ping()


class Helper(TestBase):
    """Tests for the helper functions."""

    def test_random_id(self):
        """Random IDs should always be valid."""
        for _ in range(100):
            self.assertTrue(self.is_id_valid(self.get_random_id()))

    def test_is_id_valid(self):
        """Trivial test for the is_id_valid() function."""
        self.assertTrue(self.is_id_valid("0" * 32))

        # ID has to be 32 chars.
        self.assertFalse(self.is_id_valid("0" * 31))

        # ID has to be contain only hex chars.
        self.assertFalse(self.is_id_valid("h" + "0" * 31))

    def test_is_timestamp_valid(self):
        """Trivial test for the is_timestamp_valid() function."""
        self.assertTrue(self.is_timestamp_valid(int(time.time() * 1000)))

        # Timestamp has to be positive.
        self.assertFalse(self.is_timestamp_valid(-1))

        # Timestamp can't be in the future.
        self.assertFalse(self.is_timestamp_valid(int((time.time() + 5) * 1000)))


class Miscellaneous(TestBase):
    @with_resource
    def test_same_id_different_type(self, filename: str):
        """Same IDs can be used if the types are different."""
        id_ = self.get_random_id()

        self.api.add_notebook(id_=id_)
        self.api.add_note(id_=id_)
        self.api.add_resource(id_=id_, filename=filename)
        self.api.add_tag(id_=id_)


class Regression(TestBase):
    @unittest.skipIf(not SLOW_TESTS, "Generating the long string is slow.")
    def test_long_body(self):
        """
        https://github.com/laurent22/joplin/issues/5543
        Response HTTP 104: https://stackoverflow.com/a/52826181
        """
        # Use only one random character, since it's very slow already.
        body = self.get_random_string(1) * 10 ** 9
        self.api.add_notebook()
        note_id = self.api.add_note(body=body)
        self.assertEqual(self.api.get_note(id_=note_id)["title"], body)

    def test_note_tag_fields(self):
        """https://github.com/laurent22/joplin/issues/4407"""
        self.api.add_notebook()
        note_id = self.api.add_note()
        tag_id = self.api.add_tag()
        self.api.add_tag_to_note(tag_id=tag_id, note_id=note_id)

        notes = self.api.get_notes(tag_id=tag_id, fields="id")
        self.assertEqual(list(notes["items"][0].keys()), ["id"])

    def test_set_location(self):
        """https://github.com/laurent22/joplin/issues/3884"""

    def test_add_todo(self):
        """https://github.com/laurent22/joplin/issues/1687"""


class UseCase(TestBase):
    def test_remove_spaces_from_tags(self):
        """https://www.reddit.com/r/joplinapp/comments/pozric/batch_remove_spaces_from_all_tags/"""  # noqa: E501
        self.api.add_tag(title="tag with spaces")
        self.api.add_tag(title="another tag with spaces")

        def to_camel_case(name: str) -> str:
            name = sub(r"(_|-)+", " ", name).title().replace(" ", "")
            return "".join([name[0].lower(), name[1:]])

        tags = self.api.get_tags()["items"]
        for tag in tags:
            self.api.modify_tag(id_=tag["id"], title=to_camel_case(tag["title"]))

        tags = self.api.get_tags()["items"]
        for tag in tags:
            self.assertNotIn(" ", tag["title"])
