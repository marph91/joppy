"""Interface for the joplin data API."""

import copy
import json
import logging
import sys
from typing import (
    Any,
    Callable,
    cast,
    Dict,
    List,
    MutableMapping,
    Optional,
    Union,
)
import urllib.parse

import requests


if sys.version_info >= (3, 8):
    from typing import TypedDict
else:
    from typing_extensions import TypedDict


# Don't spam the log. See: https://stackoverflow.com/a/11029841/7410886.
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


##############################################################################
# Typing support.
##############################################################################


# Datatypes used by the Joplin API. Needed for arbitrary kwargs.
JoplinTypes = Union[float, int, str]
# Kwargs mapping of the datatypes.
JoplinKwargs = MutableMapping[str, JoplinTypes]


class JoplinItem(TypedDict, total=False):
    id: str
    body: str
    title: str
    parent_id: str
    created_time: int
    updated_time: int
    type_: int
    # event specific
    type: int
    item_type: int
    item_id: str
    # resource specific
    mime: str
    filename: str
    file_extension: str
    size: int


class JoplinItemList(TypedDict, total=False):
    items: List[JoplinItem]
    has_more: bool
    cursor: int


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
        query: Optional[JoplinKwargs] = None,
        data: Optional[JoplinKwargs] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> requests.models.Response:
        logging.debug(
            f"API: {method} request: path={path}, query={query}, data={data}, "
            f"files={files}"
        )
        if data is not None and "id_" in data:
            # "id" is a reserved keyword in python, so don't use it.
            data["id"] = data["id_"]
        if query is None:
            query = {}
        query["token"] = self.token  # TODO: extending the dict may have side effects
        query_str = "&".join([f"{key}={val}" for key, val in query.items()])

        try:
            response: requests.models.Response = getattr(requests, method)(
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
        self, path: str, query: Optional[JoplinKwargs] = None
    ) -> requests.models.Response:
        """Convenience method to issue a get request."""
        return self._request("get", path, query=query)

    def post(
        self,
        path: str,
        data: Optional[JoplinKwargs] = None,
        files: Optional[Dict[str, Any]] = None,
    ) -> requests.models.Response:
        """Convenience method to issue a post request."""
        return self._request("post", path, data=data, files=files)

    def put(
        self, path: str, data: Optional[JoplinKwargs] = None
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

    def get_event(self, id_: str, **query: JoplinTypes) -> JoplinItem:
        """Get the event with the given ID."""
        response: JoplinItem = self.get(f"/events/{id_}", query=query).json()
        return response

    def get_events(self, **query: JoplinTypes) -> JoplinItemList:
        """
        Get events, paginated. To get all events (unpaginated), use
        "get_all_events()".
        """
        response: JoplinItemList = self.get("/events", query=query).json()
        return response


class Note(ApiBase):
    def add_note(self, **data: JoplinTypes) -> str:
        """Add a note."""
        response: JoplinItem = self.post("/notes", data=data).json()
        return response["id"]

    def delete_note(self, id_: str) -> None:
        """Delete a note."""
        self.delete(f"/notes/{id_}")

    def get_note(self, id_: str, **query: JoplinTypes) -> JoplinItem:
        """Get the note with the given ID."""
        response: JoplinItem = self.get(f"/notes/{id_}", query=query).json()
        return response

    def get_notes(
        self,
        notebook_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        tag_id: Optional[str] = None,
        **query: JoplinTypes,
    ) -> JoplinItemList:
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
        response: JoplinItemList = self.get(
            f"{notebook}{resource}{tag}/notes", query=query
        ).json()
        return response

    def modify_note(self, id_: str, **data: JoplinTypes) -> None:
        """Modify a note."""
        self.put(f"/notes/{id_}", data=data)


class Notebook(ApiBase):
    def add_notebook(self, **data: JoplinTypes) -> str:
        """Add a notebook."""
        response: JoplinItem = self.post("/folders", data=data).json()
        return response["id"]

    def delete_notebook(self, id_: str) -> None:
        """Delete a notebook."""
        self.delete(f"/folders/{id_}")

    def get_notebook(self, id_: str, **query: JoplinTypes) -> JoplinItem:
        """Get the notebook with the given ID."""
        response: JoplinItem = self.get(f"/folders/{id_}", query=query).json()
        return response

    def get_notebooks(self, **query: JoplinTypes) -> JoplinItemList:
        """
        Get notebooks, paginated. To get all notebooks (unpaginated), use
        "get_all_notebooks()".
        """
        response: JoplinItemList = self.get("/folders", query=query).json()
        return response

    def modify_notebook(self, id_: str, **data: JoplinTypes) -> None:
        """Modify a notebook."""
        self.put(f"/folders/{id_}", data=data)


class Ping(ApiBase):
    def ping(self) -> requests.models.Response:
        """Ping the API."""
        return self.get("/ping")


class Resource(ApiBase):
    def add_resource(self, filename: str, **data: JoplinTypes) -> str:
        """Add a resource."""
        # Preserve the filename if there is no title specified.
        if data.get("title") is None:
            data["title"] = filename
        with open(filename, "rb") as infile:
            files = {
                "data": (json.dumps(filename), infile),
                "props": (None, json.dumps(data)),
            }
            response: JoplinItem = self.post("/resources", files=files).json()
        return response["id"]

    def delete_resource(self, id_: str) -> None:
        """Delete a resource."""
        self.delete(f"/resources/{id_}")

    def get_resource(self, id_: str, **query: JoplinTypes) -> JoplinItem:
        """Get metadata about the resource with the given ID."""
        response: JoplinItem = self.get(f"/resources/{id_}", query=query).json()
        return response

    def get_resource_file(self, id_: str) -> bytes:
        """Get the resource with the given ID in binary format."""
        return self.get(f"/resources/{id_}/file").content

    def get_resources(
        self, note_id: Optional[str] = None, **query: JoplinTypes
    ) -> JoplinItemList:
        """
        Get resources, paginated. If a note ID is given, return the corresponding
        resources. To get all resources (unpaginated), use "get_all_resources()".
        """
        note = "" if note_id is None else f"/notes/{note_id}"
        response: JoplinItemList = self.get(f"{note}/resources", query=query).json()
        return response

    def modify_resource(self, id_: str, **data: JoplinTypes) -> None:
        """Modify a resource."""
        self.put(f"/resources/{id_}", data=data)


class Search(ApiBase):
    def search(self, **query: JoplinTypes) -> JoplinItemList:
        """Issue a search."""
        # Copy the dict, because its content gets changed.
        outer_query = copy.deepcopy(query)
        # The outer query is the query of the URL. The inner query is the query of the
        # Joplin search endpoint. To avoid special characters in the inner query that
        # would be recognized as outer query, encode it.
        outer_query["query"] = urllib.parse.quote(cast(str, outer_query["query"]))
        response: JoplinItemList = self.get("/search", query=outer_query).json()
        return response


class Tag(ApiBase):
    def add_tag(self, tag_id: Optional[str] = None, **data: JoplinTypes) -> str:
        """
        Add a tag. If a tag is given, add the tag to a note.
        The data has to contain the note ID.
        """
        note = "" if tag_id is None else f"/{tag_id}/notes"
        response: JoplinItem = self.post(f"/tags{note}", data=data).json()
        return response["id"]

    def delete_tag(self, id_: str, note_id: Optional[str] = None) -> None:
        """Delete a tag. If a note is given, remove the tag from this note."""
        note = "" if note_id is None else f"/notes/{note_id}"
        self.delete(f"/tags/{id_}{note}")

    def get_tag(self, id_: str, **query: JoplinTypes) -> JoplinItem:
        """Get the tag with the given ID."""
        response: JoplinItem = self.get(f"/tags/{id_}", query=query).json()
        return response

    def get_tags(
        self, note_id: Optional[str] = None, **query: JoplinTypes
    ) -> JoplinItemList:
        """
        Get tags, paginated. If a note is given, return the corresponding tags.
        To get all tags (unpaginated), use "get_all_tags()".
        """
        note = "" if note_id is None else f"/notes/{note_id}"
        response: JoplinItemList = self.get(f"{note}/tags", query=query).json()
        return response

    def modify_tag(self, id_: str, **data: JoplinTypes) -> None:
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
        self.add_tag(tag_id=tag_id, id_=note["id"])

    def add_resource_to_note(self, resource_id: str, note_id: str) -> None:
        """Add a resource to a given note."""
        note = self.get_note(id_=note_id, fields="body")
        resource = self.get_resource(id_=resource_id, fields="title")
        body_with_attachment = (
            f"{note['body']}\n![{resource['title']}](:/{resource_id})"
        )
        self.modify_note(note_id, body=body_with_attachment)

    def delete_all_notes(self) -> None:
        """Delete all notes."""
        for note in self.get_all_notes():
            self.delete_note(note["id"])

    def delete_all_notebooks(self) -> None:
        """Delete all notebooks."""
        for notebook in self.get_all_notebooks():
            # Deleting the root notebooks is sufficient.
            if not notebook["parent_id"]:
                self.delete_notebook(notebook["id"])

    def delete_all_resources(self) -> None:
        """Delete all resources."""
        for resource in self.get_all_resources():
            self.delete_resource(resource["id"])

    def delete_all_tags(self) -> None:
        """Delete all tags."""
        for tag in self.get_all_tags():
            self.delete_tag(tag["id"])

    @staticmethod
    def _unpaginate(
        func: Callable[..., JoplinItemList], **query: JoplinTypes
    ) -> List[JoplinItem]:
        """Calls an Joplin endpoint until it's response doesn't contain more data."""
        response: JoplinItemList = func(**query)
        items = response["items"]
        page = 1  # pages are one based
        while response["has_more"]:
            page += 1
            query["page"] = page
            response = func(**query)
            items.extend(response["items"])
        return items

    def get_all_events(self, **query: JoplinTypes) -> List[JoplinItem]:
        """Get all events, unpaginated."""
        return self._unpaginate(self.get_events, **query)

    def get_all_notes(self, **query: JoplinTypes) -> List[JoplinItem]:
        """Get all notes, unpaginated."""
        return self._unpaginate(self.get_notes, **query)

    def get_all_notebooks(self, **query: JoplinTypes) -> List[JoplinItem]:
        """Get all notebooks, unpaginated."""
        return self._unpaginate(self.get_notebooks, **query)

    def get_all_resources(self, **query: JoplinTypes) -> List[JoplinItem]:
        """Get all resources, unpaginated."""
        return self._unpaginate(self.get_resources, **query)

    def get_all_tags(self, **query: JoplinTypes) -> List[JoplinItem]:
        """Get all tags, unpaginated."""
        return self._unpaginate(self.get_tags, **query)

    def search_all(self, **query: JoplinTypes) -> List[JoplinItem]:
        """Issue a search and get all results, unpaginated."""
        return self._unpaginate(self.search, **query)
