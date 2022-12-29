"""Interface for the joplin data API."""

import copy
import json
import logging
from typing import (
    Any,
    Callable,
    cast,
    Dict,
    List,
    Optional,
    Union,
)
import urllib.parse

import requests

import joppy.data_types as dt


# Use a global session object for better performance.
# Define it globally to avoid "ResourceWarning".
SESSION = requests.Session()


# Don't spam the log. See: https://stackoverflow.com/a/11029841/7410886.
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


##############################################################################
# Base wrapper that manages the requests to the REST API.
##############################################################################


class ApiBase:
    """Contains the basic requests of the REST API."""

    def __init__(self, token: str, url: str = "http://localhost:41184") -> None:
        self.url = url
        self.token = token

    def _request(
        self,
        method: str,
        path: str,
        query: Optional[dt.JoplinKwargs] = None,
        data: Optional[dt.JoplinKwargs] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> requests.models.Response:
        logging.debug(
            f"API: {method} request: path={path}, query={query}, data={data}, "
            f"files={files}"
        )
        if data is not None and "id_" in data:
            # "id" is a reserved keyword in python, so don't use it.
            data["id"] = data.pop("id_")
        if query is None:
            query = {}
        query["token"] = self.token  # TODO: extending the dict may have side effects
        query_str = "&".join([f"{key}={val}" for key, val in query.items()])

        try:
            response: requests.models.Response = getattr(SESSION, method)(
                f"{self.url}{path}?{query_str}",
                json=data,
                files=files,
            )
            logging.debug(f"API: response {response.text}")
            response.raise_for_status()
        except requests.exceptions.HTTPError as err:
            err.args = err.args + (response.text,)
            raise
        return response

    def delete(self, path: str) -> requests.models.Response:
        """Convenience method to issue a delete request."""
        return self._request("delete", path)

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

    def put(
        self, path: str, data: Optional[dt.JoplinKwargs] = None
    ) -> requests.models.Response:
        """Convenience method to issue a put request."""
        return self._request("put", path, data=data)


##############################################################################
# The following classes contain all direct calls to a single endpoint.
# For further information, see: https://joplinapp.org/api/references/rest_api/
##############################################################################


class Event(ApiBase):
    """
    Events are supported since Joplin 2.4.5.
    See: https://github.com/laurent22/joplin/releases/tag/v2.4.5
    """

    def get_event(self, id_: int, **query: dt.JoplinTypes) -> dt.EventData:
        """Get the event with the given ID."""
        response = dt.EventData(**self.get(f"/events/{id_}", query=query).json())
        return response

    def get_events(self, **query: dt.JoplinTypes) -> dt.DataList[dt.EventData]:
        """
        Get events, paginated. To get all events (unpaginated), use
        "get_all_events()".
        """
        response = self.get("/events", query=query).json()
        response["items"] = [dt.EventData(**item) for item in response["items"]]
        return dt.DataList[dt.EventData](**response)


class Note(ApiBase):
    def add_note(self, **data: dt.JoplinTypes) -> str:
        """Add a note."""
        return str(self.post("/notes", data=data).json()["id"])

    def delete_note(self, id_: str) -> None:
        """Delete a note."""
        self.delete(f"/notes/{id_}")

    def get_note(self, id_: str, **query: dt.JoplinTypes) -> dt.NoteData:
        """Get the note with the given ID."""
        response = dt.NoteData(**self.get(f"/notes/{id_}", query=query).json())
        return response

    def get_notes(
        self,
        notebook_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        tag_id: Optional[str] = None,
        **query: dt.JoplinTypes,
    ) -> dt.DataList[dt.NoteData]:
        """
        Get notes, paginated. If a notebook, resource or tag ID is given,
        return the corresponding notes. To get all notes (unpaginated), use
        "get_all_notes()".
        """
        if [notebook_id, resource_id, tag_id].count(None) < 2:
            raise ValueError("Too many IDs. Specify at most one.")
        notebook = "" if notebook_id is None else f"/folders/{notebook_id}"
        resource = "" if resource_id is None else f"/resources/{resource_id}"
        tag = "" if tag_id is None else f"/tags/{tag_id}"
        response = self.get(f"{notebook}{resource}{tag}/notes", query=query).json()
        response["items"] = [dt.NoteData(**item) for item in response["items"]]
        return dt.DataList[dt.NoteData](**response)

    def modify_note(self, id_: str, **data: dt.JoplinTypes) -> None:
        """Modify a note."""
        self.put(f"/notes/{id_}", data=data)


class Notebook(ApiBase):
    def add_notebook(self, **data: dt.JoplinTypes) -> str:
        """Add a notebook."""
        return str(self.post("/folders", data=data).json()["id"])

    def delete_notebook(self, id_: str) -> None:
        """Delete a notebook."""
        self.delete(f"/folders/{id_}")

    def get_notebook(self, id_: str, **query: dt.JoplinTypes) -> dt.NotebookData:
        """Get the notebook with the given ID."""
        response = dt.NotebookData(**self.get(f"/folders/{id_}", query=query).json())
        return response

    def get_notebooks(self, **query: dt.JoplinTypes) -> dt.DataList[dt.NotebookData]:
        """
        Get notebooks, paginated. To get all notebooks (unpaginated), use
        "get_all_notebooks()".
        """
        response = self.get("/folders", query=query).json()
        response["items"] = [dt.NotebookData(**item) for item in response["items"]]
        return dt.DataList[dt.NotebookData](**response)

    def modify_notebook(self, id_: str, **data: dt.JoplinTypes) -> None:
        """Modify a notebook."""
        self.put(f"/folders/{id_}", data=data)


class Ping(ApiBase):
    def ping(self) -> requests.models.Response:
        """Ping the API."""
        return self.get("/ping")


class Resource(ApiBase):
    def add_resource(self, filename: str, **data: dt.JoplinTypes) -> str:
        """Add a resource."""
        # Preserve the filename if there is no title specified.
        if data.get("title") is None:
            data["title"] = filename
        with open(filename, "rb") as infile:
            files = {
                "data": (json.dumps(filename), infile),
                "props": (None, json.dumps(data)),
            }
            return str(self.post("/resources", files=files).json()["id"])

    def delete_resource(self, id_: str) -> None:
        """Delete a resource."""
        self.delete(f"/resources/{id_}")

    def get_resource(self, id_: str, **query: dt.JoplinTypes) -> dt.ResourceData:
        """Get metadata about the resource with the given ID."""
        response = dt.ResourceData(**self.get(f"/resources/{id_}", query=query).json())
        return response

    def get_resource_file(self, id_: str) -> bytes:
        """Get the resource with the given ID in binary format."""
        return self.get(f"/resources/{id_}/file").content

    def get_resources(
        self, note_id: Optional[str] = None, **query: dt.JoplinTypes
    ) -> dt.DataList[dt.ResourceData]:
        """
        Get resources, paginated. If a note ID is given, return the corresponding
        resources. To get all resources (unpaginated), use "get_all_resources()".
        """
        note = "" if note_id is None else f"/notes/{note_id}"
        response = self.get(f"{note}/resources", query=query).json()
        response["items"] = [dt.ResourceData(**item) for item in response["items"]]
        return dt.DataList[dt.ResourceData](**response)

    def modify_resource(self, id_: str, **data: dt.JoplinTypes) -> None:
        """Modify a resource."""
        self.put(f"/resources/{id_}", data=data)


class Search(ApiBase):
    def search(
        self, **query: dt.JoplinTypes
    ) -> Union[
        dt.DataList[dt.NoteData],
        dt.DataList[dt.NotebookData],
        dt.DataList[dt.ResourceData],
        dt.DataList[dt.TagData],
        dt.DataList[str],
    ]:
        """Issue a search."""
        # Copy the dict, because its content gets changed.
        outer_query = copy.deepcopy(query)
        # The outer query is the query of the URL. The inner query is the query of the
        # Joplin search endpoint. To avoid special characters in the inner query that
        # would be recognized as outer query, encode it.
        outer_query["query"] = urllib.parse.quote(cast(str, outer_query["query"]))
        response = self.get("/search", query=outer_query).json()
        # TODO: add missing types
        items = response["items"]
        if "type" not in query or query["type"] == dt.ItemType.NOTE.name.lower():
            response["items"] = [dt.NoteData(**item) for item in items]
            return dt.DataList[dt.NoteData](**response)
        elif query["type"] == dt.ItemType.FOLDER.name.lower():
            response["items"] = [dt.NotebookData(**item) for item in items]
            return dt.DataList[dt.NotebookData](**response)
        elif query["type"] == dt.ItemType.RESOURCE.name.lower():
            response["items"] = [dt.ResourceData(**item) for item in items]
            return dt.DataList[dt.ResourceData](**response)
        elif query["type"] == dt.ItemType.TAG.name.lower():
            response["items"] = [dt.TagData(**item) for item in items]
            return dt.DataList[dt.TagData](**response)
        elif query["type"] == dt.ItemType.MASTER_KEY.name.lower():
            return dt.DataList[str](**response)
        raise NotImplementedError(f"Type {query['type']} not implemented, yet.")


class Tag(ApiBase):
    def add_tag(self, tag_id: Optional[str] = None, **data: dt.JoplinTypes) -> str:
        """
        Add a tag. If a tag is given, add the tag to a note.
        The data has to contain the note ID.
        """
        note = "" if tag_id is None else f"/{tag_id}/notes"
        # Don't put the response into a Tag object, since it contains
        # "note_id" and "tag_id", which are undocumented.
        return str(self.post(f"/tags{note}", data=data).json()["id"])

    def delete_tag(self, id_: str, note_id: Optional[str] = None) -> None:
        """Delete a tag. If a note is given, remove the tag from this note."""
        note = "" if note_id is None else f"/notes/{note_id}"
        self.delete(f"/tags/{id_}{note}")

    def get_tag(self, id_: str, **query: dt.JoplinTypes) -> dt.TagData:
        """Get the tag with the given ID."""
        response = dt.TagData(**self.get(f"/tags/{id_}", query=query).json())
        return response

    def get_tags(
        self, note_id: Optional[str] = None, **query: dt.JoplinTypes
    ) -> dt.DataList[dt.TagData]:
        """
        Get tags, paginated. If a note is given, return the corresponding tags.
        To get all tags (unpaginated), use "get_all_tags()".
        """
        note = "" if note_id is None else f"/notes/{note_id}"
        response = self.get(f"{note}/tags", query=query).json()
        response["items"] = [dt.TagData(**item) for item in response["items"]]
        return dt.DataList[dt.TagData](**response)

    def modify_tag(self, id_: str, **data: dt.JoplinTypes) -> None:
        """Modify a tag."""
        self.put(f"/tags/{id_}", data=data)


class Api(Event, Note, Notebook, Ping, Resource, Search, Tag):
    """
    Collects all basic API functions and contains a few more useful methods.
    This should be the only class accessed from the users.
    """

    def add_tag_to_note(self, tag_id: str, note_id: str) -> None:
        """Add a tag to a given note."""
        note = self.get_note(id_=note_id, fields="id")
        assert note.id is not None
        self.add_tag(tag_id=tag_id, id_=note.id)

    def add_resource_to_note(self, resource_id: str, note_id: str) -> None:
        """Add a resource to a given note."""
        note = self.get_note(id_=note_id, fields="body")
        resource = self.get_resource(id_=resource_id, fields="title")
        body_with_attachment = f"{note.body}\n![{resource.title}](:/{resource_id})"
        self.modify_note(note_id, body=body_with_attachment)

    def delete_all_notes(self) -> None:
        """Delete all notes."""
        for note in self.get_all_notes():
            assert note.id is not None
            self.delete_note(note.id)

    def delete_all_notebooks(self) -> None:
        """Delete all notebooks."""
        for notebook in self.get_all_notebooks():
            # Deleting the root notebooks is sufficient.
            if not notebook.parent_id:
                assert notebook.id is not None
                self.delete_notebook(notebook.id)

    def delete_all_resources(self) -> None:
        """Delete all resources."""
        for resource in self.get_all_resources():
            assert resource.id is not None
            self.delete_resource(resource.id)

    def delete_all_tags(self) -> None:
        """Delete all tags."""
        for tag in self.get_all_tags():
            assert tag.id is not None
            self.delete_tag(tag.id)

    @staticmethod
    def _unpaginate(
        func: Callable[..., dt.DataList[dt.T]], **query: dt.JoplinTypes
    ) -> List[dt.T]:
        """Calls an Joplin endpoint until it's response doesn't contain more data."""
        response = func(**query)
        items = response.items
        page = 1  # pages are one based
        while response.has_more:
            page += 1
            query["page"] = page
            response = func(**query)
            items.extend(response.items)
        return items

    def get_all_events(self, **query: dt.JoplinTypes) -> List[dt.EventData]:
        """Get all events, unpaginated."""
        return self._unpaginate(self.get_events, **query)

    def get_all_notes(self, **query: dt.JoplinTypes) -> List[dt.NoteData]:
        """Get all notes, unpaginated."""
        return self._unpaginate(self.get_notes, **query)

    def get_all_notebooks(self, **query: dt.JoplinTypes) -> List[dt.NotebookData]:
        """Get all notebooks, unpaginated."""
        return self._unpaginate(self.get_notebooks, **query)

    def get_all_resources(self, **query: dt.JoplinTypes) -> List[dt.ResourceData]:
        """Get all resources, unpaginated."""
        return self._unpaginate(self.get_resources, **query)

    def get_all_tags(self, **query: dt.JoplinTypes) -> List[dt.TagData]:
        """Get all tags, unpaginated."""
        return self._unpaginate(self.get_tags, **query)

    def search_all(
        self, **query: dt.JoplinTypes
    ) -> List[Union[dt.NoteData, dt.NotebookData, dt.ResourceData, dt.TagData]]:
        """Issue a search and get all results, unpaginated."""
        return self._unpaginate(self.search, **query)  # type: ignore
