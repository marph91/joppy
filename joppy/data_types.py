"""Typing support for Joplin's data API."""

from dataclasses import dataclass, field, fields
from datetime import datetime
import enum
import mimetypes
from typing import (
    Generic,
    List,
    MutableMapping,
    Optional,
    Union,
    Set,
    TypeVar,
)
import uuid


# Datatypes used by the Joplin API. Needed for arbitrary kwargs.
JoplinTypes = Union[float, int, str]
# Kwargs mapping of the datatypes.
JoplinKwargs = MutableMapping[str, JoplinTypes]


class EventChangeType(enum.IntEnum):
    # https://joplinapp.org/api/references/rest_api/#properties-4
    CREATED = 1
    UPDATED = 2
    DELETED = 3


class ItemType(enum.IntEnum):
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


class MarkupLanguage(enum.IntEnum):
    # https://discourse.joplinapp.org/t/api-body-vs-body-html/11697/4
    MARKDOWN = 1
    HTML = 2


def is_id_valid(id_: str) -> bool:
    """Check whether a string is a valid id."""
    if len(id_) == 32:
        # client ID
        # https://joplinapp.org/api/references/rest_api/#creating-a-note-with-a-specific-id
        # https://stackoverflow.com/a/11592279/7410886
        try:
            int(id_, 16)
            return True
        except ValueError:
            return False
    if len(id_) == 22:
        # server ID
        # https://joplinapp.org/help/dev/spec/server_items/
        return True
    return False


@dataclass
class BaseData:
    type_: Optional[ItemType] = None

    def __post_init__(self) -> None:
        # detect if data is encrypted
        encryption_applied = getattr(self, "encryption_applied", False)
        if encryption_applied is not None and bool(int(encryption_applied)):
            raise NotImplementedError("Encryption is not supported")

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
            elif (
                field_.name.endswith("_time")
                or field_.name.endswith("Time")
                or field_.name
                in (
                    "todo_due",
                    "todo_completed",
                )
            ):
                try:
                    value_int = int(value)
                    casted_value = (
                        None
                        if value_int == 0
                        # TODO: Replace by "fromtimestamp()" when
                        # minimum Python version is 3.11.
                        else datetime.utcfromtimestamp(value_int / 1000.0)
                    )
                    setattr(self, field_.name, casted_value)
                except ValueError:
                    # TODO: This is not spec conform.
                    casted_value = datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ")
                    setattr(self, field_.name, casted_value)
            elif field_.name in (
                "is_conflict",
                "is_todo",
                "encryption_applied",
                "is_shared",
                "encryption_blob_encrypted",
            ):
                setattr(self, field_.name, bool(int(value)))
            elif field_.name == "latitude":
                setattr(self, field_.name, float(value))
                if not (-90 <= float(value) <= 90):
                    raise ValueError("Invalid latitude:", value)
            elif field_.name == "longitude":
                setattr(self, field_.name, float(value))
                if not (-180 <= float(value) <= 180):
                    raise ValueError("Invalid longitude:", value)
            elif field_.name == "markup_language":
                setattr(self, field_.name, MarkupLanguage(int(value)))
            # elif field_.name == "order":
            # elif field_.name == "crop_rect":
            # elif field_.name == "icon":
            # elif field_.name == "filename":  # "file_extension"
            elif field_.name in ("item_type", "type_"):
                setattr(self, field_.name, ItemType(int(value)))
            elif field_.name == "type":
                setattr(self, field_.name, EventChangeType(int(value)))

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

    def __str__(self) -> str:
        # show only fields with values
        not_none_fields = ", ".join(
            f"{field.name}={getattr(self, field.name)}"
            for field in fields(self)
            if getattr(self, field.name) is not None
        )
        return f"{type(self).__name__}({not_none_fields})"


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
    todo_completed: Optional[datetime] = None
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
    user_data: Optional[str] = None
    deleted_time: Optional[datetime] = None
    body_html: Optional[str] = None
    base_url: Optional[str] = None
    image_data_url: Optional[str] = None
    crop_rect: Optional[str] = None

    def serialize(self) -> str:
        # title is needed always to prevent problems with body
        # f. e. when there is a newline at start
        lines = ["" if self.title is None else self.title, ""]
        if self.body is not None:
            lines.extend([self.body, ""])
        for field_ in fields(self):
            if field_.name == "id":
                # ID is always required
                if self.id is None:
                    self.id = uuid.uuid4().hex
                lines.append(f"{field_.name}: {self.id}")
            elif field_.name == "markup_language":
                # required to get an editable note
                if self.markup_language is None:
                    self.markup_language = MarkupLanguage.MARKDOWN
                lines.append(f"{field_.name}: {self.markup_language}")
            elif field_.name == "source_application":
                if self.source_application is None:
                    self.source_application = "joppy"
                lines.append(f"{field_.name}: {self.source_application}")
            elif field_.name in ("title", "body"):
                pass  # handled before
            elif field_.name == "type_":
                self.item_type = ItemType.NOTE
                lines.append(f"{field_.name}: {self.item_type}")
            elif field_.name == "updated_time":
                # required, even if empty
                value_raw = getattr(self, field_.name)
                value = "" if value_raw is None else value_raw
                lines.append(f"{field_.name}: {value}")
            else:
                value_raw = getattr(self, field_.name)
                if value_raw is not None:
                    lines.append(f"{field_.name}: {value_raw}")
        return "\n".join(lines)


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
    user_data: Optional[str] = None
    deleted_time: Optional[datetime] = None

    def serialize(self) -> str:
        lines = []
        if self.title is not None:
            lines.extend([self.title, ""])
        for field_ in fields(self):
            if field_.name == "id":
                # ID is always required
                if self.id is None:
                    self.id = uuid.uuid4().hex
                lines.append(f"{field_.name}: {self.id}")
            elif field_.name == "title":
                pass  # handled before
            elif field_.name == "type_":
                self.item_type = ItemType.FOLDER
                lines.append(f"{field_.name}: {self.item_type}")
            elif field_.name == "updated_time":
                # required, even if empty
                value_raw = getattr(self, field_.name)
                value = "" if value_raw is None else value_raw
                lines.append(f"{field_.name}: {value}")
            else:
                value_raw = getattr(self, field_.name)
                if value_raw is not None:
                    lines.append(f"{field_.name}: {value_raw}")
        return "\n".join(lines)


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
    user_data: Optional[str] = None
    blob_updated_time: Optional[datetime] = None
    ocr_text: Optional[str] = None
    ocr_details: Optional[str] = None
    ocr_status: Optional[int] = None
    ocr_error: Optional[str] = None

    @staticmethod
    def default_fields() -> Set[str]:
        return {"id", "title"}

    def serialize(self) -> str:
        lines = []
        if self.title is not None:
            lines.extend([self.title, ""])
        # TODO: file_extension, size
        for field_ in fields(self):
            if field_.name == "id":
                # ID is always required
                if self.id is None:
                    self.id = uuid.uuid4().hex
                lines.append(f"{field_.name}: {self.id}")
            elif field_.name == "mime":
                # mime is always required
                if self.mime is None:
                    mime_type, _ = mimetypes.guess_type(self.filename or "")
                    self.mime = (
                        mime_type
                        if mime_type is not None
                        else "application/octet-stream"
                    )
                lines.append(f"{field_.name}: {self.mime}")
            elif field_.name == "title":
                pass  # handled before
            elif field_.name == "type_":
                self.item_type = ItemType.RESOURCE
                lines.append(f"{field_.name}: {self.item_type}")
            elif field_.name == "updated_time":
                # required, even if empty
                value_raw = getattr(self, field_.name)
                value = "" if value_raw is None else value_raw
                lines.append(f"{field_.name}: {value}")
            else:
                value_raw = getattr(self, field_.name)
                if value_raw is not None:
                    lines.append(f"{field_.name}: {value_raw}")
        return "\n".join(lines)


@dataclass
class RevisionData(BaseData):
    """https://joplinapp.org/help/api/references/rest_api/#revisions"""

    id: Optional[str] = None
    parent_id: Optional[str] = None
    item_type: Optional[ItemType] = None
    item_id: Optional[str] = None
    item_updated_time: Optional[datetime] = None
    title_diff: Optional[str] = None
    body_diff: Optional[str] = None
    metadata_diff: Optional[str] = None
    encryption_cipher_text: Optional[str] = None
    encryption_applied: Optional[bool] = None
    updated_time: Optional[datetime] = None
    created_time: Optional[datetime] = None

    @staticmethod
    def default_fields() -> Set[str]:
        return {"id"}


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
    user_data: Optional[str] = None

    def serialize(self) -> str:
        lines = []
        if self.title is not None:
            lines.extend([self.title, ""])
        for field_ in fields(self):
            if field_.name == "id":
                # ID is always required
                if self.id is None:
                    self.id = uuid.uuid4().hex
                lines.append(f"{field_.name}: {self.id}")
            elif field_.name == "title":
                pass  # handled before
            elif field_.name == "type_":
                self.item_type = ItemType.TAG
                lines.append(f"{field_.name}: {self.item_type}")
            elif field_.name == "updated_time":
                # required, even if empty
                value_raw = getattr(self, field_.name)
                value = "" if value_raw is None else value_raw
                lines.append(f"{field_.name}: {value}")
            else:
                value_raw = getattr(self, field_.name)
                if value_raw is not None:
                    lines.append(f"{field_.name}: {value_raw}")
        return "\n".join(lines)


@dataclass
class NoteTagData(BaseData):
    """Links a tag to a note."""

    id: Optional[str] = None
    note_id: Optional[str] = None
    tag_id: Optional[str] = None
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None
    user_created_time: Optional[datetime] = None
    user_updated_time: Optional[datetime] = None
    encryption_cipher_text: Optional[str] = None
    encryption_applied: Optional[bool] = None
    is_shared: Optional[bool] = None

    def serialize(self) -> str:
        lines = []
        for field_ in fields(self):
            if field_.name == "id":
                # ID is always required
                if self.id is None:
                    self.id = uuid.uuid4().hex
                lines.append(f"{field_.name}: {self.id}")
            elif field_.name == "type_":
                self.item_type = ItemType.NOTE_TAG
                lines.append(f"{field_.name}: {self.item_type}")
            elif field_.name == "updated_time":
                # required, even if empty
                value_raw = getattr(self, field_.name)
                value = "" if value_raw is None else value_raw
                lines.append(f"{field_.name}: {value}")
            else:
                value_raw = getattr(self, field_.name)
                if value_raw is not None:
                    lines.append(f"{field_.name}: {value_raw}")
        return "\n".join(lines)


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


class LockType(enum.IntEnum):
    NONE = 0
    SYNC = 1
    EXCLUSIVE = 2


class LockClientType(enum.IntEnum):
    DESKTOP = 1
    MOBILE = 2
    CLI = 3


@dataclass
class LockData(BaseData):
    """
    https://joplinapp.org/help/dev/spec/sync_lock#lock-files
    https://github.com/laurent22/joplin/blob/b617a846964ea49be2ffefd31439e911ad84ed8c/packages/server/src/routes/api/locks.ts
    """

    id: Optional[str] = None
    type: Optional[LockType] = None
    clientId: Optional[str] = None
    clientType: Optional[LockClientType] = None
    updatedTime: Optional[datetime] = None


@dataclass
class UserData(BaseData):
    """
    https://joplinapp.org/help/dev/spec/server_user_status/
    https://github.com/laurent22/joplin/blob/fc516d05b3c9564a54fd0fbb9a1886739190bba0/packages/server/src/services/database/types.ts#L246
    """

    id: Optional[str] = None
    email: Optional[str] = None
    password: Optional[str] = None
    is_admin: Optional[bool] = None
    full_name: Optional[str] = None
    created_time: Optional[datetime] = None
    updated_time: Optional[datetime] = None
    email_confirmed: Optional[bool] = None
    must_set_password: Optional[bool] = None
    account_type: Optional[int] = None  # TODO: enum
    can_upload: Optional[bool] = None
    max_item_size: Optional[int] = None
    max_total_item_size: Optional[int] = None
    total_item_size: Optional[int] = None
    can_share_folder: Optional[bool] = None
    can_share_note: Optional[bool] = None
    can_receive_folder: Optional[bool] = None
    enabled: Optional[bool] = None
    disabled_time: Optional[datetime] = None
    is_external: Optional[bool] = None
    sso_auth_code: Optional[str] = None
    sso_auth_code_expire_at: Optional[datetime] = None


AnyData = Union[
    EventData, NoteData, NotebookData, NoteTagData, ResourceData, RevisionData, TagData
]


T = TypeVar(
    "T",
    EventData,
    NoteData,
    NotebookData,
    ResourceData,
    RevisionData,
    TagData,
    LockData,
    UserData,
    str,
)


@dataclass
class DataList(Generic[T]):
    has_more: bool
    cursor: Optional[int] = None
    items: List[T] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Cast the basic joplin API datatypes to more convenient datatypes.
        self.has_more = bool(self.has_more)
