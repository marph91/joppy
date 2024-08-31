import logging
import pathlib
from typing import Any, cast, Dict, List, Optional, Union

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
    body_splitted = body.split("\n\n")

    def extract_metadata(serialized_metadata: str) -> Dict[Any, Any]:
        metadata = {}
        for line in serialized_metadata.split("\n"):
            key, value = line.split(": ", 1)
            if not value:
                continue
            metadata[key] = value
        return metadata

    if len(body_splitted) == 1:
        # metadata only
        title = None
        note_body = None
        metadata = extract_metadata(body_splitted[0])
    elif len(body_splitted) == 2:
        # title + metadata
        title = body_splitted[0]
        note_body = None
        metadata = extract_metadata(body_splitted[1])
    elif len(body_splitted) == 3:
        # title + body + metadata
        title = body_splitted[0]
        note_body = body_splitted[1]
        metadata = extract_metadata(body_splitted[2])
    else:
        print("TODO: ", body_splitted)

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

        # cookie is saved in session and used for the next requests
        self.post("/login", data={"email": self.user, "password": password})

    def _request(
        self,
        method: str,
        path: str,
        query: Optional[dt.JoplinKwargs] = None,
        data: Any = None,
        files: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, Any]] = None,
    ) -> requests.models.Response:
        LOGGER.debug(f"API: {method} request: path={path}, query={query}, data={data}")
        if query is None:
            query = {}
        query_str = "&".join([f"{key}={val}" for key, val in query.items()])

        try:
            response: requests.models.Response = getattr(SESSION, method)(
                f"{self.url}{path}?{query_str}",
                data=data,
                files=files,
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
    ) -> requests.models.Response:
        """Convenience method to issue a post request."""
        return self._request("post", path, data=data, files=files)

    def put(self, path: str, data: Union[str, bytes]) -> requests.models.Response:
        """Convenience method to issue a put request."""
        return self._request(
            "put", path, data=data, headers={"Content-Type": "application/octet-stream"}
        )


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

    def get_notes(self) -> dt.DataList[dt.NoteData]:
        response = self.get("/api/items/root:/:/children").json()
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

    def get_notebooks(self) -> dt.DataList[dt.NotebookData]:
        response = self.get("/api/items/root:/:/children").json()
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

    def get_resources(self) -> dt.DataList[dt.ResourceData]:
        """
        Get resources, paginated.
        To get all resources (unpaginated), use "get_all_resources()".
        """
        response = self.get("/api/items/root:/:/children").json()
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

    def get_revision(self, id_: str, **query: Any) -> dt.RevisionData:
        """Get the revision with the given ID."""
        response = self.get(f"/api/items/root:/{add_suffix(id_)}:/content")
        return cast(dt.RevisionData, deserialize(response.text))

    def get_revisions(self, **query: Any) -> dt.DataList[dt.RevisionData]:
        response = self.get("/api/items/root:/:/children").json()
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

    def get_tags(self) -> dt.DataList[dt.TagData]:
        """
        Get tags, paginated.
        To get all tags (unpaginated), use "get_all_tags()".
        """
        response = self.get("/api/items/root:/:/children").json()
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
    def get_users(self) -> dt.DataList[dt.UserData]:
        """
        Get users, paginated.
        To get all users (unpaginated), use "get_all_users()".
        """
        response = self.get("/api/users").json()
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

    def get_all_notes(self, **query: Any) -> List[dt.NoteData]:
        """Get all notes, unpaginated."""
        return tools._unpaginate(self.get_notes, **query)

    def get_all_notebooks(self, **query: Any) -> List[dt.NotebookData]:
        """Get all notebooks, unpaginated."""
        return tools._unpaginate(self.get_notebooks, **query)

    def get_all_resources(self, **query: Any) -> List[dt.ResourceData]:
        """Get all resources, unpaginated."""
        return tools._unpaginate(self.get_resources, **query)

    def get_all_revisions(self, **query: Any) -> List[dt.RevisionData]:
        """Get all revisions, unpaginated."""
        return tools._unpaginate(self.get_revisions, **query)

    def get_all_tags(self, **query: Any) -> List[dt.TagData]:
        """Get all tags, unpaginated."""
        return tools._unpaginate(self.get_tags, **query)

    def get_all_users(self, **query: Any) -> List[dt.UserData]:
        """Get all users, unpaginated."""
        return tools._unpaginate(self.get_users, **query)

    def show_user_permissions(self) -> None:
        """https://joplinapp.org/help/dev/spec/server_user_status/#user-status"""
        current_user = None
        for user in self.get_all_users():
            if user.email == self.user:
                current_user = user
                break
        if current_user is None:
            print(f"User {self.user} not found.")
        else:
            print(f"{current_user.enabled=}, {current_user.can_upload=}")
