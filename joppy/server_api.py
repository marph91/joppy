from contextlib import contextmanager
import datetime
import logging
import pathlib
import time
from typing import Any, cast, Dict, List, Optional, Tuple, Union
import uuid

import requests

import joppy.data_types as dt
from joppy import tools


# Use a global session object for better performance.
# Define it globally to avoid "ResourceWarning".
SESSION = requests.Session()

# Don't spam the log. See: https://stackoverflow.com/a/11029841/7410886.
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

LOGGER = logging.getLogger("joppy")


def deserialize(body: str) -> Optional[dt.AnyData]:
    """Deserialize server data from string to a known data type."""

    # https://github.com/laurent22/joplin/blob/b617a846964ea49be2ffefd31439e911ad84ed8c/packages/lib/models/BaseItem.ts#L549-L596
    def extract_metadata(serialized_metadata: str) -> Dict[Any, Any]:
        metadata = {}
        for line in serialized_metadata.split("\n"):
            key, value = line.split(": ", 1)
            if not value:
                continue
            metadata[key] = value
        return metadata

    metadata_splitted = body.rsplit("\n\n", 1)
    if len(metadata_splitted) == 1:
        # metadata only
        title = None
        note_body = None
        metadata = extract_metadata(metadata_splitted[0])
    else:
        metadata = extract_metadata(metadata_splitted[1])
        title_splitted = metadata_splitted[0].split("\n\n", 1)
        if len(title_splitted) == 1:
            # title + metadata
            title = title_splitted[0]
            note_body = None
        else:
            # title + body + metadata
            title = title_splitted[0]
            note_body = title_splitted[1]

    if title is not None:
        metadata["title"] = title
    if note_body is not None:
        metadata["body"] = note_body

    item_type = dt.ItemType(int(metadata["type_"]))
    if item_type == dt.ItemType.NOTE:
        return dt.NoteData(**metadata)
    elif item_type == dt.ItemType.FOLDER:
        return dt.NotebookData(**metadata)
    elif item_type == dt.ItemType.RESOURCE:
        return dt.ResourceData(**metadata)
    elif item_type == dt.ItemType.TAG:
        return dt.TagData(**metadata)
    elif item_type == dt.ItemType.NOTE_TAG:
        return dt.NoteTagData(**metadata)
    elif item_type == dt.ItemType.REVISION:
        # ignore revisions for now
        pass
    else:
        print("TODO: ", dt.ItemType(int(metadata["type_"])))
    return None


def add_suffix(string: str, suffix: str = ".md") -> str:
    """Add a suffix."""
    return str(pathlib.Path(string).with_suffix(suffix))


def remove_suffix(string: str) -> str:
    """Remove the suffix."""
    return str(pathlib.Path(string).with_suffix(""))


##############################################################################
# Base wrapper that manages the requests to the client REST API.
##############################################################################


class LockError(Exception):
    pass


class ApiBase:
    """Contains the basic requests of the server REST API."""

    def __init__(
        self,
        user: str = "admin@localhost",
        password: str = "admin",
        url: str = "http://localhost:22300",
    ) -> None:
        self.user = user
        self.url = url
        self.client_id = uuid.uuid4().hex
        self.current_sync_lock: Optional[dt.LockData] = None
        # TODO: Where to get it?
        # https://github.com/laurent22/joplin/blob/b617a846964ea49be2ffefd31439e911ad84ed8c/packages/lib/services/synchronizer/LockHandler.ts#L145
        self.lock_ttl = datetime.timedelta(seconds=60 * 3)
        self.lock_auto_refresh_interval = datetime.timedelta(seconds=60)

        # cookie is saved in session and used for the next requests
        self.post("/login", data={"email": self.user, "password": password})

        # check for compatible sync version
        sync_version = self.get_sync_version()
        if sync_version is None:
            LOGGER.warning("Sync version not found. Creating a new file.")
            # https://joplinapp.org/help/dev/spec/sync#sync-target-properties
            now = int(time.time() * 1000)
            sync_target_info = {
                "version": 3,
                "e2ee": {"value": False, "updatedTime": now},
                "activeMasterKeyId": {"value": False, "updatedTime": now},
                "masterKeys": [],
                "ppk": {},
                "appMinVersion": "3.0.0",
            }
            self.put("/api/items/root:/info.json:/content", json=sync_target_info)
        else:
            if sync_version != 3:
                raise NotImplementedError(
                    f"Only server version 3 is supported. Found version {sync_version}."
                )

    def get_sync_version(self) -> Optional[int]:
        try:
            response = self.get("/api/items/root:/info.json:/content")
            server_info = response.json()
            return int(server_info["version"])
        except requests.exceptions.HTTPError as error_json:
            if error_json.response.status_code == 404:
                try:
                    response = self.get("/api/items/root:/.sync/version.txt:/content")
                    return int(response.text)
                except requests.exceptions.HTTPError as error_txt:
                    if error_txt.response.status_code == 404:
                        return None  # in this case, a new one should be created
                    else:
                        raise error_txt
            else:
                raise error_json

    def _request(
        self,
        method: str,
        path: str,
        query: Optional[dt.JoplinKwargs] = None,
        data: Any = None,
        files: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
    ) -> requests.models.Response:
        # bypass the lock for info, lock and login requests
        if not (
            path == "/login"
            or path.startswith("/api/locks")
            or "info.json" in path
            or ".sync/version.txt" in path
        ):
            if self.current_sync_lock is None:
                raise LockError("No sync lock. Acquire a lock before issuing requests.")
            assert self.current_sync_lock.updatedTime is not None  # for mypy
            if not self._is_lock_active(self.current_sync_lock.updatedTime):
                raise LockError(
                    "Sync lock expired. Delete the lock before issuing requests."
                )
            elif (
                self.current_sync_lock.updatedTime + self.lock_auto_refresh_interval
                < datetime.datetime.utcnow()
            ):
                LOGGER.debug("Refreshing sync lock.")
                self.current_sync_lock = self._add_lock()

        LOGGER.debug(f"API: {method} request: path={path}, query={query}, data={data}")
        if query is None:
            query = {}
        query_str = "&".join([f"{key}={val}" for key, val in query.items()])

        try:
            response: requests.models.Response = getattr(SESSION, method)(
                f"{self.url}{path}?{query_str}",
                data=data,
                files=files,
                json=json,
                headers=headers,
            )
            LOGGER.debug(f"API: response {response.text}")
            response.raise_for_status()
        except requests.exceptions.HTTPError as err:
            err.args = err.args + (response.text,)
            raise
        return response

    def delete(
        self, path: str, query: Optional[dt.JoplinKwargs] = None
    ) -> requests.models.Response:
        """Convenience method to issue a delete request."""
        return self._request("delete", path, query=query)

    def get(
        self, path: str, query: Optional[dt.JoplinKwargs] = None
    ) -> requests.models.Response:
        """Convenience method to issue a get request."""
        return self._request("get", path, query=query)

    def post(
        self,
        path: str,
        data: Optional[dt.JoplinKwargs] = None,
        files: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> requests.models.Response:
        """Convenience method to issue a post request."""
        return self._request("post", path, data=data, files=files, json=json)

    def put(
        self,
        path: str,
        data: Optional[Union[str, bytes]] = None,
        json: Optional[Dict[str, Any]] = None,
    ) -> requests.models.Response:
        """Convenience method to issue a put request."""
        return self._request(
            "put",
            path,
            data=data,
            json=json,
            headers={"Content-Type": "application/octet-stream"},
        )

    ##############################################################################
    # Lock functionality
    ##############################################################################

    def _add_lock(self) -> dt.LockData:
        """Add or refresh a lock."""
        data = {
            "type": dt.LockType.SYNC,
            "clientId": self.client_id,
            "clientType": dt.LockClientType.DESKTOP,
        }
        response = self.post("/api/locks", json=data)
        return dt.LockData(**response.json())

    def _delete_lock(
        self, lock_type: dt.LockType, client_type: dt.LockClientType, client_id: str
    ) -> None:
        """
        Delete a lock.
        https://joplinapp.org/help/dev/spec/sync_lock#lock-files
        """
        self.delete(f"/api/locks/{lock_type}_{client_type}_{client_id}")

    def _get_locks(self, **query: dt.JoplinTypes) -> dt.DataList[dt.LockData]:
        """
        Get locks, paginated.
        To get all locks (unpaginated), use "_get_all_locks()".
        """
        response = self.get("/api/locks", query=query).json()
        response["items"] = [dt.LockData(**item) for item in response["items"]]
        return dt.DataList[dt.LockData](**response)

    def _get_all_locks(self) -> List[dt.LockData]:
        """Get all locks, unpaginated."""
        return tools._unpaginate(self._get_locks)

    def _is_lock_active(self, updated_time: datetime.datetime) -> bool:
        return updated_time + self.lock_ttl > datetime.datetime.utcnow()

    def _acquire_sync_lock(self, tries: int = 1) -> None:
        """
        Acquire a sync lock.
        https://joplinapp.org/help/dev/spec/sync_lock#acquiring-a-sync-lock
        """
        # TODO: check sync target version
        # https://joplinapp.org/help/dev/spec/sync_lock#sync-target-migration

        def is_locked(
            check_lock_types: Tuple[dt.LockType, ...] = (
                dt.LockType.SYNC,
                dt.LockType.EXCLUSIVE,
            ),
        ) -> bool:
            # https://github.com/laurent22/joplin/blob/b617a846964ea49be2ffefd31439e911ad84ed8c/packages/lib/services/synchronizer/LockHandler.ts#L72-L75
            for lock in self._get_all_locks():
                if lock.type not in check_lock_types:
                    continue
                assert lock.updatedTime is not None
                if self._is_lock_active(lock.updatedTime):
                    if lock.type == dt.LockType.EXCLUSIVE:
                        return True
                    elif (
                        lock.type == dt.LockType.SYNC
                        and lock.clientId == self.client_id
                    ):
                        return True
                    # If there is no exclusive lock and no lock with our ID,
                    # sync is allowed.
            return False

        for delay in range(tries):
            if not is_locked():
                self.current_sync_lock = self._add_lock()
                if is_locked(check_lock_types=(dt.LockType.EXCLUSIVE,)):
                    # avoid race conditions
                    self._delete_own_lock()
                else:
                    return
            time.sleep(delay)
            LOGGER.debug("sync target is still locked")

    def _delete_own_lock(self) -> None:
        self.current_sync_lock = None
        self._delete_lock(dt.LockType.SYNC, dt.LockClientType.DESKTOP, self.client_id)

    @contextmanager
    def sync_lock(self) -> Any:
        self._acquire_sync_lock()
        if self.current_sync_lock is None:
            raise LockError("Couldn't aqcuire sync lock")
        yield
        self._delete_own_lock()


##############################################################################
# Specific classes
##############################################################################


class Note(ApiBase):
    def add_note(self, parent_id: str, **data: Any) -> str:
        """Add a note."""
        # Parent ID is required. Else the notes are created at root.
        note_data = dt.NoteData(parent_id=parent_id, **data)
        request_data = note_data.serialize()
        assert note_data.id is not None
        # Access all files by full path for now:
        # https://joplinapp.org/help/dev/spec/server_file_url_format
        self.put(
            f"/api/items/root:/{add_suffix(note_data.id)}:/content", data=request_data
        )
        return note_data.id

    def delete_note(self, id_: str) -> None:
        """Delete a note."""
        self.delete(f"/api/items/root:/{add_suffix(id_)}:")

    def get_note(self, id_: str) -> dt.NoteData:
        response = self.get(f"/api/items/root:/{add_suffix(id_)}:/content")
        return cast(dt.NoteData, deserialize(response.text))

    def get_notes(self, **query: dt.JoplinTypes) -> dt.DataList[dt.NoteData]:
        response = self.get("/api/items/root:/:/children", query=query).json()
        # TODO: Is this the best practice?
        notes = []
        for item in response["items"]:
            if item["name"].endswith(".md"):
                item_complete = self.get_note(remove_suffix(item["name"]))
                if isinstance(item_complete, dt.NoteData):
                    notes.append(item_complete)
        return dt.DataList(response["has_more"], response["cursor"], notes)

    def modify_note(self, id_: str, **data: Any) -> None:
        """Modify a note."""
        # TODO: Without fetching the orginal note, this would be replacing,
        # not modifying.
        id_server = add_suffix(id_)
        note_data = self.get_note(id_server)
        for key, value in data.items():
            setattr(note_data, key, value)
        request_data = note_data.serialize()
        self.put(f"/api/items/root:/{id_server}:/content", data=request_data)


class Notebook(ApiBase):
    def add_notebook(self, **data: Any) -> str:
        """Add a notebook."""
        notebook_data = dt.NotebookData(**data)
        request_data = notebook_data.serialize()
        assert notebook_data.id is not None
        self.put(
            f"/api/items/root:/{add_suffix(notebook_data.id)}:/content",
            data=request_data,
        )
        return notebook_data.id

    def delete_notebook(self, id_: str) -> None:
        """Delete a notebook."""
        self.delete(f"/api/items/root:/{add_suffix(id_)}:")

    def get_notebook(self, id_: str) -> dt.NotebookData:
        response = self.get(f"/api/items/root:/{add_suffix(id_)}:/content")
        return cast(dt.NotebookData, deserialize(response.text))

    def get_notebooks(self, **query: dt.JoplinTypes) -> dt.DataList[dt.NotebookData]:
        response = self.get("/api/items/root:/:/children", query=query).json()
        # TODO: Is this the best practice?
        notebooks = []
        for item in response["items"]:
            if item["name"].endswith(".md"):
                item_complete = self.get_notebook(remove_suffix(item["name"]))
                if isinstance(item_complete, dt.NotebookData):
                    notebooks.append(item_complete)
        return dt.DataList(response["has_more"], response["cursor"], notebooks)

    def modify_notebook(self, id_: str, **data: Any) -> None:
        """Modify a notebook."""
        # TODO: Without fetching the orginal notebook, this would be replacing,
        # not modifying.
        id_server = add_suffix(id_)
        notebook_data = self.get_notebook(id_server)
        for key, value in data.items():
            setattr(notebook_data, key, value)
        request_data = notebook_data.serialize()
        self.put(f"/api/items/root:/{id_server}:/content", data=request_data)


class Ping(ApiBase):
    def ping(self) -> requests.models.Response:
        """Ping the API."""
        return self.get("/api/ping")


class Resource(ApiBase):
    def add_resource(self, filename: str, **data: Any) -> str:
        """Add a resource."""

        # add the corresponding md item with metadata
        title = str(data.pop("title", filename))
        resource_data = dt.ResourceData(title=title, filename=filename, **data)
        request_data = resource_data.serialize()
        assert resource_data.id is not None
        self.put(
            f"/api/items/root:/{add_suffix(resource_data.id)}:/content",
            data=request_data,
        )

        # add the resource itself
        self.put(
            f"/api/items/root:/.resource/{resource_data.id}:/content",
            data=pathlib.Path(filename).read_bytes(),
        )

        return resource_data.id

    def delete_resource(self, id_: str) -> None:
        """Delete a resource."""
        # metadata
        self.delete(f"/api/items/root:/{add_suffix(id_)}:")
        # resource itself
        self.delete(f"/api/items/root:/.resource/{id_}:")

    def get_resource(self, id_: str) -> dt.ResourceData:
        """Get metadata about the resource with the given ID."""
        response = self.get(f"/api/items/root:/{add_suffix(id_)}:/content")
        return cast(dt.ResourceData, deserialize(response.text))

    def get_resource_file(self, id_: str) -> bytes:
        """Get the resource with the given ID in binary format."""
        return self.get(f"/api/items/root:/.resource/{id_}:/content").content

    def get_resources(self, **query: dt.JoplinTypes) -> dt.DataList[dt.ResourceData]:
        """
        Get resources, paginated.
        To get all resources (unpaginated), use "get_all_resources()".
        """
        response = self.get("/api/items/root:/:/children", query=query).json()
        # TODO: Is this the best practice?
        resources = []
        for item in response["items"]:
            if item["name"].endswith(".md"):
                item_complete = self.get_resource(remove_suffix(item["name"]))
                if isinstance(item_complete, dt.ResourceData):
                    resources.append(item_complete)
        return dt.DataList(response["has_more"], response["cursor"], resources)

    def modify_resource(self, id_: str, **data: Any) -> None:
        """Modify a resource."""
        # TODO: split in metadata and content?
        raise NotImplementedError("'modify_resource()' is not yet implemented")


class Revision(ApiBase):
    def delete_revision(self, id_: str) -> None:
        """Delete a revision."""
        self.delete(f"/api/items/root:/{add_suffix(id_)}:")

    def get_revision(self, id_: str) -> dt.RevisionData:
        """Get the revision with the given ID."""
        response = self.get(f"/api/items/root:/{add_suffix(id_)}:/content")
        return cast(dt.RevisionData, deserialize(response.text))

    def get_revisions(self, **query: Any) -> dt.DataList[dt.RevisionData]:
        response = self.get("/api/items/root:/:/children", query=query).json()
        # TODO: Is this the best practice?
        revisions = []
        for item in response["items"]:
            if item["name"].endswith(".md"):
                item_complete = self.get_revision(remove_suffix(item["name"]))
                if isinstance(item_complete, dt.RevisionData):
                    revisions.append(item_complete)
        return dt.DataList(response["has_more"], response["cursor"], revisions)


class Tag(ApiBase):
    def add_tag(self, **data: Any) -> str:
        """Add a tag."""
        tag_data = dt.TagData(**data)
        request_data = tag_data.serialize()
        assert tag_data.id is not None
        self.put(
            f"/api/items/root:/{add_suffix(tag_data.id)}:/content", data=request_data
        )
        return tag_data.id

    def delete_tag(self, id_: str) -> None:
        """Delete a tag."""
        self.delete(f"/api/items/root:/{add_suffix(id_)}:")

    def get_tag(self, id_: str) -> dt.TagData:
        """Get the tag with the given ID."""
        response = self.get(f"/api/items/root:/{add_suffix(id_)}:/content")
        return cast(dt.TagData, deserialize(response.text))

    def get_tags(self, **query: dt.JoplinTypes) -> dt.DataList[dt.TagData]:
        """
        Get tags, paginated.
        To get all tags (unpaginated), use "get_all_tags()".
        """
        response = self.get("/api/items/root:/:/children", query=query).json()
        # TODO: Is this the best practice?
        tags = []
        for item in response["items"]:
            if item["name"].endswith(".md"):
                item_complete = self.get_tag(remove_suffix(item["name"]))
                if isinstance(item_complete, dt.TagData):
                    tags.append(item_complete)
        return dt.DataList(response["has_more"], response["cursor"], tags)

    def modify_tag(self, id_: str, **data: Any) -> None:
        """Modify a tag."""
        # TODO: Without fetching the orginal tag, this would be replacing,
        # not modifying.
        id_server = add_suffix(id_)
        tag_data = self.get_tag(id_server)
        for key, value in data.items():
            setattr(tag_data, key, value)
        request_data = tag_data.serialize()
        self.put(f"/api/items/root:/{id_server}:/content", data=request_data)


class User(ApiBase):
    def get_users(self, **query: dt.JoplinTypes) -> dt.DataList[dt.UserData]:
        """
        Get users, paginated.
        To get all users (unpaginated), use "get_all_users()".
        """
        response = self.get("/api/users", query=query).json()
        response["items"] = [dt.UserData(**item) for item in response["items"]]
        return dt.DataList[dt.UserData](**response)


class ServerApi(Note, Notebook, Ping, Resource, Revision, Tag, User):
    """
    Collects all basic API functions and contains a few more useful methods.
    This should be the only class accessed from the users.
    """

    def add_tag_to_note(self, tag_id: str, note_id: str) -> str:
        """Add a tag to a given note."""
        note_tag_data = dt.NoteTagData(tag_id=tag_id, note_id=note_id)
        request_data = note_tag_data.serialize()
        assert note_tag_data.id is not None
        self.put(
            f"/api/items/root:/{add_suffix(note_tag_data.id)}:/content",
            data=request_data,
        )
        return note_tag_data.id

    def add_resource_to_note(self, resource_id: str, note_id: str) -> None:
        """Add a resource to a given note."""
        note = self.get_note(id_=note_id)
        resource = self.get_resource(id_=resource_id)
        # TODO: Use "assertIsNotNone()" when
        # https://github.com/python/mypy/issues/5528 is resolved.
        assert resource.mime is not None
        image_prefix = "!" if resource.mime.startswith("image/") else ""
        original_body = "" if note.body is None else note.body
        body_with_attachment = (
            f"{original_body}\n{image_prefix}[{resource.title}](:/{resource_id})"
        )
        self.modify_note(note_id, body=body_with_attachment)

    def delete_all_notes(self) -> None:
        """Delete all notes permanently."""
        for note in self.get_all_notes():
            assert note.id is not None
            self.delete_note(note.id)

    def delete_all_notebooks(self) -> None:
        """Delete all notebooks permanently."""
        for notebook in self.get_all_notebooks():
            assert notebook.id is not None
            self.delete_notebook(notebook.id)

    def delete_all_resources(self) -> None:
        """Delete all resources."""
        for resource in self.get_all_resources():
            assert resource.id is not None
            self.delete_resource(resource.id)

    def delete_all_revisions(self) -> None:
        """Delete all revisions."""
        for revision in self.get_all_revisions():
            assert revision.id is not None
            self.delete_revision(revision.id)

    def delete_all_tags(self) -> None:
        """Delete all tags."""
        for tag in self.get_all_tags():
            assert tag.id is not None
            self.delete_tag(tag.id)

    def get_all_notes(self) -> List[dt.NoteData]:
        """Get all notes, unpaginated."""
        return tools._unpaginate(self.get_notes)

    def get_all_notebooks(self) -> List[dt.NotebookData]:
        """Get all notebooks, unpaginated."""
        return tools._unpaginate(self.get_notebooks)

    def get_all_resources(self) -> List[dt.ResourceData]:
        """Get all resources, unpaginated."""
        return tools._unpaginate(self.get_resources)

    def get_all_revisions(self) -> List[dt.RevisionData]:
        """Get all revisions, unpaginated."""
        return tools._unpaginate(self.get_revisions)

    def get_all_tags(self) -> List[dt.TagData]:
        """Get all tags, unpaginated."""
        return tools._unpaginate(self.get_tags)

    def get_all_users(self) -> List[dt.UserData]:
        """Get all users, unpaginated."""
        return tools._unpaginate(self.get_users)

    def get_current_user(self) -> Optional[dt.UserData]:
        """https://joplinapp.org/help/dev/spec/server_user_status/#user-status"""
        current_user = None
        for user in self.get_all_users():
            if user.email == self.user:
                current_user = user
                break
        return current_user
