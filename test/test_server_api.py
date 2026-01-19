"""Tests for the Joplin server python API."""

import string
import time
from typing import cast
import unittest

from joppy.server_api import deserialize, LockError, ServerApi
import joppy.data_types as dt
from . import common, setup_joplin


API = None
SERVER = None


def setUpModule():  # pylint: disable=invalid-name
    global API, SERVER
    SERVER = setup_joplin.JoplinServer()
    # login only once to prevent
    # "429 Client Error: Too Many Requests for url: http://localhost:22300/login"
    API = ServerApi()


def tearDownModule():  # pylint: disable=invalid-name
    if SERVER is not None:
        SERVER.stop()


class ServerBase(common.Base):
    api: ServerApi

    def setUp(self):
        self.api = cast(ServerApi, API)
        with self.api.sync_lock():  # needed for clearing all data
            super().setUp()

        self.api._acquire_sync_lock()
        if self.api.current_sync_lock is None:
            raise LockError("Couldn't aqcuire sync lock")

    def tearDown(self):
        super().tearDown()
        self.api._delete_own_lock()


class Note(ServerBase):
    def test_add(self):
        """Add a note to an existing notebook."""
        parent_id = self.api.add_notebook()
        id_ = self.api.add_note(parent_id=parent_id)

        notes = self.api.get_notes().items
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0].id, id_)
        self.assertEqual(notes[0].parent_id, parent_id)

    def test_delete(self):
        """Add and then delete a note."""
        parent_id = self.api.add_notebook()
        id_ = self.api.add_note(parent_id)
        notes = self.api.get_notes()
        self.assertEqual(len(notes.items), 1)

        self.api.delete_note(id_=id_)
        self.assertEqual(self.api.get_notes().items, [])

    def test_get_note(self):
        """Get a specific note."""
        parent_id = self.api.add_notebook()
        id_ = self.api.add_note(parent_id=parent_id)
        note = self.api.get_note(id_=id_)
        self.assertEqual(note.type_, dt.ItemType.NOTE)

    def test_get_notes(self):
        """Get all notes."""
        parent_id = self.api.add_notebook()
        self.api.add_note(parent_id=parent_id)
        notes = self.api.get_notes()
        self.assertEqual(len(notes.items), 1)
        self.assertFalse(notes.has_more)

    def test_get_all_notes(self):
        """Get all notes, unpaginated."""
        parent_id = self.api.add_notebook()
        count = 101  # pagination seems to start at 100 items
        for _ in range(count):
            self.api.add_note(parent_id)
        self.assertEqual(len(self.api.get_all_notes()), count)

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
        note = self.api.get_note(id_=id_)
        self.assertEqual(note.parent_id, notebook_2_id)

        # Ensure the original properties aren't modified.
        self.assertEqual(note.body, original_body)
        self.assertEqual(note.title, original_title)


class Notebook(ServerBase):
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
        self.assertEqual(notebook.type_, dt.ItemType.FOLDER)

    def test_get_notebooks(self):
        """Get all notebooks."""
        self.api.add_notebook()
        notebooks = self.api.get_notebooks()
        self.assertEqual(len(notebooks.items), 1)
        self.assertFalse(notebooks.has_more)

    def test_get_all_notebooks(self):
        """Get all notebooks, unpaginated."""
        count = 101
        for _ in range(count):
            self.api.add_notebook()
        self.assertEqual(len(self.api.get_all_notebooks()), count)

    def test_move(self):
        """Move a root notebok to another notebook. It's now a subnotebook."""
        first_id = self.api.add_notebook()
        second_id = self.api.add_notebook()
        self.assertEqual(self.api.get_notebook(id_=first_id).parent_id, None)
        self.assertEqual(self.api.get_notebook(id_=second_id).parent_id, None)

        self.api.modify_notebook(id_=first_id, parent_id=second_id)
        self.assertEqual(self.api.get_notebook(id_=first_id).parent_id, second_id)
        self.assertEqual(self.api.get_notebook(id_=second_id).parent_id, None)


class Ping(ServerBase):
    def test_ping(self):
        """Ping should return the test string."""
        ping = self.api.ping()
        self.assertEqual(
            ping.json(), {"status": "ok", "message": "Joplin Server is running"}
        )


class Resource(ServerBase):
    @common.with_resource
    def test_add(self, filename):
        """Add a resource."""
        id_ = self.api.add_resource(filename=filename)

        resources = self.api.get_resources().items
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0].id, id_)

    @common.with_resource
    def test_add_to_note(self, filename):
        """Add a resource to an existing note."""
        parent_id = self.api.add_notebook()
        for file_ in ("test/grant_authorization_button.png", filename):
            with self.subTest(file_=file_):
                note_id = self.api.add_note(parent_id)
                resource_id = self.api.add_resource(filename=file_)
                self.api.add_resource_to_note(resource_id=resource_id, note_id=note_id)

                # Get the resource
                resource = self.api.get_resource(id_=resource_id)

                # Verify the markdown is correct (prefix "!" for images).
                note = self.api.get_note(id_=note_id)
                # TODO: Use "assertIsNotNone()" when
                # https://github.com/python/mypy/issues/5528 is resolved.
                assert resource.mime is not None
                image_prefix = "!" if resource.mime.startswith("image/") else ""
                self.assertEqual(
                    f"\n{image_prefix}[{file_}](:/{resource_id})", note.body
                )

    @common.with_resource
    def test_delete(self, filename):
        """Add and then delete a resource."""
        id_ = self.api.add_resource(filename=filename)
        resources = self.api.get_resources()
        self.assertEqual(len(resources.items), 1)

        self.api.delete_resource(id_=id_)
        self.assertEqual(self.api.get_resources().items, [])

    @common.with_resource
    def test_get_resource(self, filename):
        """Get metadata about a specific resource."""
        id_ = self.api.add_resource(filename=filename)
        resource = self.api.get_resource(id_=id_)
        self.assertEqual(resource.type_, dt.ItemType.RESOURCE)

    @common.with_resource
    def test_get_resource_file(self, filename):
        """Get a specific resource in binary format."""
        for file_ in ("test/grant_authorization_button.png", filename):
            id_ = self.api.add_resource(filename=file_)
            resource = self.api.get_resource_file(id_=id_)
            with open(file_, "rb") as resource_file:
                self.assertEqual(resource, resource_file.read())

    @common.with_resource
    def test_get_resources(self, filename):
        """Get all resources."""
        self.api.add_resource(filename=filename)
        resources = self.api.get_resources()
        self.assertEqual(len(resources.items), 1)
        self.assertFalse(resources.has_more)

    @common.with_resource
    def test_get_all_resources(self, filename):
        """Get all resources, unpaginated."""
        count = 5
        for _ in range(count):
            self.api.add_resource(filename=filename)
        self.assertEqual(len(self.api.get_all_resources()), count)

    # @common.with_resource
    # def test_modify_title(self, filename):
    #     """Modify a resource title."""
    #     id_ = self.api.add_resource(filename=filename)

    #     new_title = self.get_random_string(exclude=string.whitespace)
    #     self.api.modify_resource(id_=id_, title=new_title)
    #     self.assertEqual(self.api.get_resource(id_=id_).title, new_title)

    @common.with_resource
    def test_check_property_title(self, filename):
        """Check the title of a resource."""
        # newline seems to be stripped from the title
        title = self.get_random_string(exclude=string.whitespace)
        id_ = self.api.add_resource(filename=filename, title=title)
        resource = self.api.get_resource(id_=id_)
        self.assertEqual(resource.title, title)


class Tag(ServerBase):
    def test_add_no_note(self):
        """Tags can be added even without notes."""
        id_ = self.api.add_tag()

        tags = self.api.get_tags().items
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0].id, id_)

    def test_add_to_note(self):
        """Add a tag to an existing note."""
        parent_id = self.api.add_notebook()
        note_id = self.api.add_note(parent_id)
        tag_id = self.api.add_tag()
        self.api.add_tag_to_note(tag_id=tag_id, note_id=note_id)

        tags = self.api.get_all_tags()
        self.assertEqual(len(tags), 1)

    def test_add_with_parent(self):
        """Add a tag as child for an existing note."""
        notebook_id = self.api.add_notebook()
        parent_id = self.api.add_note(notebook_id)
        id_ = self.api.add_tag(parent_id=parent_id)

        tags = self.api.get_tags().items
        self.assertEqual(len(tags), 1)
        self.assertEqual(tags[0].id, id_)
        self.assertEqual(tags[0].parent_id, parent_id)

    def test_get_tag(self):
        """Get a specific tag."""
        id_ = self.api.add_tag()
        tag = self.api.get_tag(id_=id_)
        self.assertEqual(tag.type_, dt.ItemType.TAG)

    def test_get_tags(self):
        """Get all tags."""
        self.api.add_tag()
        tags = self.api.get_tags()
        self.assertEqual(len(tags.items), 1)
        self.assertFalse(tags.has_more)

    def test_get_all_tags(self):
        """Get all tags, unpaginated."""
        count = 101
        for _ in range(count):
            self.api.add_tag()
        self.assertEqual(len(self.api.get_all_tags()), count)


class Lock(ServerBase):
    def test_sync_lock_different_id(self):
        self.assertEqual(len(self.api._get_all_locks()), 1)

        # Acquiring a second sync lock with a different client ID should succeed.
        second_api = ServerApi()
        with second_api.sync_lock():
            self.assertEqual(len(self.api._get_all_locks()), 2)
        self.assertEqual(len(self.api._get_all_locks()), 1)

    def test_sync_lock_same_id(self):
        self.assertEqual(len(self.api._get_all_locks()), 1)

        # Acquiring a second sync lock with the same client ID should fail.
        with self.assertRaises(LockError):
            second_api = ServerApi()
            second_api.client_id = self.api.client_id
            with second_api.sync_lock():
                self.fail("This should never happen")

        self.assertEqual(len(self.api._get_all_locks()), 1)

    @unittest.skipIf(not common.SLOW_TESTS, "Waiting for the timeout takes some time.")
    def test_sync_lock_refresh(self):
        locks = self.api._get_all_locks()
        self.assertEqual(len(locks), 1)
        assert locks[0].updatedTime is not None
        updated_time_before = locks[0].updatedTime

        # refresh interval is not needed -> same lock
        self.api.get_all_notebooks()
        locks = self.api._get_all_locks()
        self.assertEqual(len(locks), 1)
        assert locks[0].updatedTime is not None
        self.assertEqual(locks[0].updatedTime, updated_time_before)

        # some arbitrary request to refresh the sync lock
        time.sleep(self.api.lock_auto_refresh_interval.total_seconds() + 1)
        self.api.get_all_notebooks()

        locks = self.api._get_all_locks()
        self.assertEqual(len(locks), 1)
        assert locks[0].updatedTime is not None
        self.assertGreater(locks[0].updatedTime, updated_time_before)

    @unittest.skipIf(not common.SLOW_TESTS, "Waiting for the timeout takes some time.")
    def test_sync_lock_expired(self):
        locks = self.api._get_all_locks()
        self.assertEqual(len(locks), 1)

        time.sleep(self.api.lock_ttl.total_seconds() + 1)
        # lock should be expired after self.api.lock_ttl.total_seconds()
        with self.assertRaises(LockError):
            self.api.get_all_notebooks()


class User(ServerBase):
    def test_get_current_user(self):
        """The current user should be available and have read and write permissions."""
        current_user = self.api.get_current_user()
        assert current_user is not None
        # TODO: Use self.assertIsNotNone(current_user) when mypy supports it.
        self.assertTrue(current_user.enabled)
        self.assertTrue(current_user.can_upload)


class Deserialize(ServerBase):
    def test_note_only_metadata(self):
        body = "id: 0e8d296dbef34588b0de060630ad2582\ntype_: 1"
        result = deserialize(body)

        # TODO: use assertIsInstance() when mypy understands it
        assert isinstance(result, dt.NoteData)
        self.assertEqual(result.id, "0e8d296dbef34588b0de060630ad2582")
        self.assertIsNone(result.title)
        self.assertIsNone(result.body)

    def test_note_title_metadata(self):
        body = "note2\n\nid: 0e8d296dbef34588b0de060630ad2582\ntype_: 1"
        result = deserialize(body)

        # TODO: use assertIsInstance() when mypy understands it
        assert isinstance(result, dt.NoteData)
        self.assertEqual(result.id, "0e8d296dbef34588b0de060630ad2582")
        self.assertEqual(result.title, "note2")
        self.assertIsNone(result.body)

    def test_note_title_body_metadata(self):
        body = (
            "note2\n\nbody\n\nwith some\n\nnewlines\n\n"
            "id: 0e8d296dbef34588b0de060630ad2582\ntype_: 1"
        )
        result = deserialize(body)

        # TODO: use assertIsInstance() when mypy understands it
        assert isinstance(result, dt.NoteData)
        self.assertEqual(result.id, "0e8d296dbef34588b0de060630ad2582")
        self.assertEqual(result.title, "note2")
        self.assertEqual(result.body, "body\n\nwith some\n\nnewlines")
