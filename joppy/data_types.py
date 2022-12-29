"""Typing support for Joplin's data API."""

from dataclasses import dataclass, field, fields
from datetime import datetime
import enum
from typing import (
    Generic,
    List,
    MutableMapping,
    Optional,
    Union,
    Set,
    TypeVar,
)


# Datatypes used by the Joplin API. Needed for arbitrary kwargs.
JoplinTypes = Union[float, int, str]
# Kwargs mapping of the datatypes.
JoplinKwargs = MutableMapping[str, JoplinTypes]


class EventChangeType(enum.Enum):
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


class MarkupLanguage(enum.Enum):
    # https://discourse.joplinapp.org/t/api-body-vs-body-html/11697/4
    MARKDOWN = 1
    HTML = 2


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


@dataclass
class BaseData:
    type_: Optional[ItemType] = None

    def __post_init__(self) -> None:
        # Cast the basic joplin API datatypes to more convenient datatypes.
        for field_ in fields(self):
            value = getattr(self, field_.name)
            if value is None:
                continue
            if field_.name in (
                "id",
                "parent_id",
                "share_id",
                "conflict_original_id",
                "master_key_id",
                "item_id",
            ):
                # Exclude integer and empty string IDs.
                if value and isinstance(value, str) and not is_id_valid(value):
                    raise ValueError("Invalid ID:", value)
            elif field_.name.endswith("_time") or field_.name == "todo_due":
                setattr(self, field_.name, datetime.fromtimestamp(value / 1000.0))
            elif field_.name in (
                "is_conflict",
                "is_todo",
                "todo_completed",
                "encryption_applied",
                "is_shared",
                "encryption_blob_encrypted",
            ):
                setattr(self, field_.name, bool(value))
            elif field_.name == "latitude":
                if not (-90 <= value <= 90):
                    raise ValueError("Invalid latitude:", value)
            elif field_.name == "longitude":
                if not (-180 <= value <= 180):
                    raise ValueError("Invalid longitude:", value)
            # elif field_.name == "order":
            # elif field_.name == "crop_rect":
            # elif field_.name == "icon":
            # elif field_.name == "filename":  # "file_extension"
            elif field_.name in ("item_type", "type_"):
                setattr(self, field_.name, ItemType(value))
            elif field_.name == "type":
                setattr(self, field_.name, EventChangeType(value))

    def assigned_fields(self) -> Set[str]:
        # Exclude "type_" for convenience.
        return set(
            field_.name
            for field_ in fields(self)
            if getattr(self, field_.name) is not None and field_.name != "type_"
        )

    @classmethod
    def fields(cls) -> Set[str]:
        # Exclude "type_" for convenience.
        return set(field_.name for field_ in fields(cls) if field_.name != "type_")

    @staticmethod
    def default_fields() -> Set[str]:
        return {"id", "parent_id", "title"}


@dataclass
class NoteData(BaseData):
    """https://joplinapp.org/api/references/rest_api/#notes"""

    id: Optional[str] = None
    parent_id: Optional[str] = None
    title: Optional[str] = None
    body: Optional[str] = None
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None
    is_conflict: Optional[bool] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    altitude: Optional[float] = None
    author: Optional[str] = None
    source_url: Optional[str] = None
    is_todo: Optional[bool] = None
    todo_due: Optional[datetime] = None
    todo_completed: Optional[bool] = None
    source: Optional[str] = None
    source_application: Optional[str] = None
    application_data: Optional[str] = None
    order: Optional[float] = None
    user_created_time: Optional[datetime] = None
    user_updated_time: Optional[datetime] = None
    encryption_cipher_text: Optional[str] = None
    encryption_applied: Optional[bool] = None
    markup_language: Optional[MarkupLanguage] = None
    is_shared: Optional[bool] = None
    share_id: Optional[str] = None
    conflict_original_id: Optional[str] = None
    master_key_id: Optional[str] = None
    body_html: Optional[str] = None
    base_url: Optional[str] = None
    image_data_url: Optional[str] = None
    crop_rect: Optional[str] = None


@dataclass
class NotebookData(BaseData):
    """https://joplinapp.org/api/references/rest_api/#folders"""

    id: Optional[str] = None
    title: Optional[str] = None
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None
    user_created_time: Optional[datetime] = None
    user_updated_time: Optional[datetime] = None
    encryption_cipher_text: Optional[str] = None
    encryption_applied: Optional[bool] = None
    parent_id: Optional[str] = None
    is_shared: Optional[bool] = None
    share_id: Optional[str] = None
    master_key_id: Optional[str] = None
    icon: Optional[str] = None


@dataclass
class ResourceData(BaseData):
    """https://joplinapp.org/api/references/rest_api/#resources"""

    id: Optional[str] = None
    title: Optional[str] = None
    mime: Optional[str] = None
    filename: Optional[str] = None
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None
    user_created_time: Optional[datetime] = None
    user_updated_time: Optional[datetime] = None
    file_extension: Optional[str] = None
    encryption_cipher_text: Optional[str] = None
    encryption_applied: Optional[bool] = None
    encryption_blob_encrypted: Optional[bool] = None
    size: Optional[int] = None
    is_shared: Optional[bool] = None
    share_id: Optional[str] = None
    master_key_id: Optional[str] = None

    @staticmethod
    def default_fields() -> Set[str]:
        return {"id", "title"}


@dataclass
class TagData(BaseData):
    """https://joplinapp.org/api/references/rest_api/#tags"""

    id: Optional[str] = None
    title: Optional[str] = None
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None
    user_created_time: Optional[datetime] = None
    user_updated_time: Optional[datetime] = None
    encryption_cipher_text: Optional[str] = None
    encryption_applied: Optional[bool] = None
    is_shared: Optional[bool] = None
    parent_id: Optional[str] = None


@dataclass
class EventData(BaseData):
    """https://joplinapp.org/api/references/rest_api/#events"""

    id: Optional[int] = None
    item_type: Optional[ItemType] = None
    item_id: Optional[int] = None
    type: Optional[EventChangeType] = None
    created_time: Optional[datetime] = None
    # source: Optional[int] = None
    # before_change_item: Optional[str] = None

    def __post_init__(self) -> None:
        super().__post_init__()
        # Cast the basic joplin API datatypes to more convenient datatypes.
        if self.id is not None:
            self.id = int(self.id)

    @staticmethod
    def default_fields() -> Set[str]:
        return {"id", "item_type", "item_id", "type", "created_time"}


T = TypeVar("T", EventData, NoteData, NotebookData, ResourceData, TagData, str)


@dataclass
class DataList(Generic[T]):
    has_more: bool
    cursor: Optional[int] = None
    items: List[T] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Cast the basic joplin API datatypes to more convenient datatypes.
        self.has_more = bool(self.has_more)
