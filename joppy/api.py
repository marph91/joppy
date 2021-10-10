"""Interface for the joplin data API."""

import json
import logging
from typing import Optional

import requests


# Don't spam the log. See: https://stackoverflow.com/a/11029841/7410886.
logging.getLogger("requests").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)


class ApiBase:
    """Contains the basic requests of the REST API."""

    def __init__(self, token: str, url: str = "http://localhost:41184"):
        self.url = url
        self.token = token

    def _request(
        self,
        method: str,
        path: str,
        query: Optional[dict] = None,
        data: Optional[dict] = None,
        **kwargs,
    ):
        logging.debug(f"API: {method} request: {path=}, {query=}, {data=}, {kwargs=}")
        if data is not None:
            # "id" is a reserved keyword in python, so don't use it.
            data["id"] = data.pop("id_", None)
        if query is None:
            query = {}
        query["token"] = self.token  # TODO: extending the dict may have side effects
        query_str = "&".join([f"{key}={val}" for key, val in query.items()])

        try:
            response = getattr(requests, method)(
                f"{self.url}{path}?{query_str}", json=data, **kwargs
            )
            logging.debug(f"API: response {response.text}")
            response.raise_for_status()
        except requests.exceptions.HTTPError as err:
            err.args = err.args + (response.text,)
            raise
        return response

    def delete(self, *args):
        """Convenience method to issue a delete request."""
        return self._request("delete", *args)

    def get(self, *args, **kwargs):
        """Convenience method to issue a get request."""
        return self._request("get", *args, **kwargs)

    def post(self, *args, **kwargs):
        """Convenience method to issue a post request."""
        return self._request("post", *args, **kwargs)

    def put(self, *args, **kwargs):
        """Convenience method to issue a put request."""
        return self._request("put", *args, **kwargs)


##############################################################################
# The following classes contain all direct calls to a single endpoint.
# For further information, see: https://joplinapp.org/api/references/rest_api/
##############################################################################


class Event(ApiBase):
    def get_event(self, id_: str, **kwargs):
        """Get the event with the given ID."""
        return self.get(f"/events/{id_}", query=kwargs).json()

    def get_events(self, **kwargs):
        """Get all events."""
        return self.get("/events", query=kwargs).json()


class Note(ApiBase):
    def add_note(self, **kwargs) -> str:
        """Add a note."""
        response = self.post("/notes", data=kwargs)
        return response.json()["id"]

    def delete_note(self, id_: str):
        """Delete a note."""
        self.delete(f"/notes/{id_}")

    def get_note(self, id_: str, **kwargs):
        """Get the note with the given ID."""
        return self.get(f"/notes/{id_}", query=kwargs).json()

    def get_notes(
        self,
        notebook_id: Optional[str] = None,
        resource_id: Optional[str] = None,
        tag_id: Optional[str] = None,
        **kwargs,
    ):
        """
        Get all notes. If a notebook, resource or tag ID is given,
        return all corresponding notes.
        """
        if [notebook_id, resource_id, tag_id].count(None) < 2:
            raise ValueError("Too many IDs. Specify at most one.")
        notebook = "" if notebook_id is None else f"/folders/{notebook_id}"
        resource = "" if resource_id is None else f"/resources/{resource_id}"
        tag = "" if tag_id is None else f"/tags/{tag_id}"
        return self.get(f"{notebook}{resource}{tag}/notes", query=kwargs).json()

    def modify_note(self, id_: str, **kwargs):
        """Modify a note."""
        self.put(f"/notes/{id_}", data=kwargs)


class Notebook(ApiBase):
    def add_notebook(self, **kwargs) -> str:
        """Add a notebook."""
        response = self.post("/folders", data=kwargs)
        return response.json()["id"]

    def delete_notebook(self, id_: str):
        """Delete a notebook."""
        self.delete(f"/folders/{id_}")

    def get_notebook(self, id_: str, **kwargs):
        """Get the notebook with the given ID."""
        return self.get(f"/folders/{id_}", query=kwargs).json()

    def get_notebooks(self, **kwargs):
        """Get all notebooks."""
        return self.get("/folders", query=kwargs).json()

    def modify_notebook(self, id_: str, **kwargs):
        """Modify a notebook."""
        self.put(f"/folders/{id_}", data=kwargs)


class Ping(ApiBase):
    def ping(self):
        """Ping the API."""
        return self.get("/ping")


class Resource(ApiBase):
    def add_resource(self, filename: str, **kwargs) -> str:
        """Add a resource."""
        with open(filename, "rb") as infile:
            files = {
                "data": (json.dumps(filename), infile),
                "props": (None, json.dumps(kwargs)),
            }
            response = self.post("/resources", files=files, data=kwargs)
        return response.json()["id"]

    def delete_resource(self, id_: str):
        """Delete a resource."""
        self.delete(f"/resources/{id_}")

    def get_resource(self, id_: str, get_file: bool = False, **kwargs):
        """Get the resource with the given ID."""
        file_ = "/file" if get_file else ""
        return self.get(f"/resources/{id_}{file_}", query=kwargs).json()

    def get_resources(self, note_id: Optional[str] = None, **kwargs):
        """Get all notes. If a note ID is given, return all resources of this note."""
        note = "" if note_id is None else f"/notes/{note_id}"
        return self.get(f"{note}/resources", query=kwargs).json()

    def modify_resource(self, id_: str, **kwargs):
        """Modify a resource."""
        self.put(f"/resources/{id_}", data=kwargs)


class Search(ApiBase):
    def search(self, **kwargs):
        """Issue a search."""
        response = self.get("/search", query=kwargs)
        return response.json()


class Tag(ApiBase):
    def add_tag(self, tag_id: Optional[str] = None, **kwargs) -> str:
        """
        Add a tag. If a tag is given, add the tag to a note.
        The data has to contain the note ID.
        """
        note = "" if tag_id is None else f"/{tag_id}/notes"
        response = self.post(f"/tags{note}", data=kwargs)
        return response.json()["id"]

    def delete_tag(self, id_: str, note_id: Optional[str] = None):
        """Delete a tag. If a note is given, remove the tag from this note."""
        note = "" if note_id is None else f"/notes/{note_id}"
        self.delete(f"/tags/{id_}{note}")

    def get_tag(self, id_: str, **kwargs):
        """Get the tag with the given ID."""
        return self.get(f"/tags/{id_}", query=kwargs).json()

    def get_tags(self, note_id: Optional[str] = None, **kwargs):
        """Get all tags. If a note is given, return all tags of this note."""
        note = "" if note_id is None else f"/notes/{note_id}"
        return self.get(f"{note}/tags", query=kwargs).json()

    def modify_tag(self, id_: str, **kwargs):
        """Modify a tag."""
        self.put(f"/tags/{id_}", data=kwargs)


class Api(Event, Note, Notebook, Ping, Resource, Search, Tag):
    """
    Collects all basic API functions and contains a few more useful methods.
    This should be the only class accessed from the users.
    """

    def add_tag_to_note(self, tag_id: str, note_id: str):
        """Add a tag to a given note."""
        note = self.get_note(id_=note_id, fields="id")
        self.add_tag(tag_id=tag_id, id_=note["id"])

    def delete_all_notebooks(self):
        """Delete all notebooks."""
        notebooks = self.get_notebooks()["items"]
        for notebook in notebooks:
            # Deleting the root notebooks is sufficient.
            if not notebook["parent_id"]:
                self.delete_notebook(notebook["id"])

    def delete_all_resources(self):
        """Delete all resources."""
        resources = self.get_resources()["items"]
        for resource in resources:
            self.delete_resource(resource["id"])

    def delete_all_tags(self):
        """Delete all tags."""
        tags = self.get_tags()["items"]
        for tag in tags:
            self.delete_tag(tag["id"])

    def get_all_events(self, **kwargs):
        """Get all events unpaginated."""
        page = 0
        response = self.get_events(**kwargs)
        events = response["items"]
        while response["has_more"]:
            response = self.get_events(page=page, **kwargs)
            events.append(response["items"])
            page += 1
        return events
