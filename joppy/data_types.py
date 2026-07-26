"""Typing support for Joplin's data API."""

import datetime as dt
import enum
import mimetypes
import uuid
from collections.abc import MutableMapping
from dataclasses import dataclass, field, fields
from typing import Generic, TypeVar

# Datatypes used by the Joplin API. Needed for arbitrary kwargs.
JoplinTypes = float | int | str
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
    # server ID
    # https://joplinapp.org/help/dev/spec/server_items/
    return len(id_) == 22


@dataclass
class BaseData:
    type_: ItemType | None = None

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
                        else dt.datetime.fromtimestamp(value_int / 1000.0, tz=dt.UTC)
                    )
                    setattr(self, field_.name, casted_value)
                except ValueError:
                    # TODO: This is not spec conform.
                    casted_value = dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f").replace(tzinfo=dt.UTC)
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

    def assigned_fields(self) -> set[str]:
        # Exclude "type_" for convenience.
        return {
            field_.name
            for field_ in fields(self)
            if getattr(self, field_.name) is not None and field_.name != "type_"
        }

    @classmethod
    def fields(cls) -> set[str]:
        # Exclude "type_" for convenience.
        return {field_.name for field_ in fields(cls) if field_.name != "type_"}

    @staticmethod
    def default_fields() -> set[str]:
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

    id: str | None = None
    parent_id: str | None = None
    title: str | None = None
    body: str | None = None
    created_time: dt.datetime | None = None
    updated_time: dt.datetime | None = None
    is_conflict: bool | None = None
    latitude: float | None = None
    longitude: float | None = None
    altitude: float | None = None
    author: str | None = None
    source_url: str | None = None
    is_todo: bool | None = None
    todo_due: dt.datetime | None = None
    todo_completed: dt.datetime | None = None
    source: str | None = None
    source_application: str | None = None
    application_data: str | None = None
    order: float | None = None
    user_created_time: dt.datetime | None = None
    user_updated_time: dt.datetime | None = None
    encryption_cipher_text: str | None = None
    encryption_applied: bool | None = None
    markup_language: MarkupLanguage | None = None
    is_shared: bool | None = None
    share_id: str | None = None
    conflict_original_id: str | None = None
    master_key_id: str | None = None
    user_data: str | None = None
    deleted_time: dt.datetime | None = None
    body_html: str | None = None
    base_url: str | None = None
    image_data_url: str | None = None
    crop_rect: str | None = None

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

    id: str | None = None
    title: str | None = None
    created_time: dt.datetime | None = None
    updated_time: dt.datetime | None = None
    user_created_time: dt.datetime | None = None
    user_updated_time: dt.datetime | None = None
    encryption_cipher_text: str | None = None
    encryption_applied: bool | None = None
    parent_id: str | None = None
    is_shared: bool | None = None
    share_id: str | None = None
    master_key_id: str | None = None
    icon: str | None = None
    user_data: str | None = None
    deleted_time: dt.datetime | None = None

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

    id: str | None = None
    title: str | None = None
    mime: str | None = None
    filename: str | None = None
    created_time: dt.datetime | None = None
    updated_time: dt.datetime | None = None
    user_created_time: dt.datetime | None = None
    user_updated_time: dt.datetime | None = None
    file_extension: str | None = None
    encryption_cipher_text: str | None = None
    encryption_applied: bool | None = None
    encryption_blob_encrypted: bool | None = None
    size: int | None = None
    is_shared: bool | None = None
    share_id: str | None = None
    master_key_id: str | None = None
    user_data: str | None = None
    blob_updated_time: dt.datetime | None = None
    ocr_text: str | None = None
    ocr_details: str | None = None
    ocr_status: int | None = None
    ocr_error: str | None = None

    @staticmethod
    def default_fields() -> set[str]:
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

    id: str | None = None
    parent_id: str | None = None
    item_type: ItemType | None = None
    item_id: str | None = None
    item_updated_time: dt.datetime | None = None
    title_diff: str | None = None
    body_diff: str | None = None
    metadata_diff: str | None = None
    encryption_cipher_text: str | None = None
    encryption_applied: bool | None = None
    updated_time: dt.datetime | None = None
    created_time: dt.datetime | None = None

    @staticmethod
    def default_fields() -> set[str]:
        return {"id"}


@dataclass
class TagData(BaseData):
    """https://joplinapp.org/api/references/rest_api/#tags"""

    id: str | None = None
    title: str | None = None
    created_time: dt.datetime | None = None
    updated_time: dt.datetime | None = None
    user_created_time: dt.datetime | None = None
    user_updated_time: dt.datetime | None = None
    encryption_cipher_text: str | None = None
    encryption_applied: bool | None = None
    is_shared: bool | None = None
    parent_id: str | None = None
    user_data: str | None = None

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

    id: str | None = None
    note_id: str | None = None
    tag_id: str | None = None
    created_time: dt.datetime | None = None
    updated_time: dt.datetime | None = None
    user_created_time: dt.datetime | None = None
    user_updated_time: dt.datetime | None = None
    encryption_cipher_text: str | None = None
    encryption_applied: bool | None = None
    is_shared: bool | None = None

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

    id: int | None = None
    item_type: ItemType | None = None
    item_id: int | None = None
    type: EventChangeType | None = None
    created_time: dt.datetime | None = None
    # source: Optional[int] = None
    # before_change_item: Optional[str] = None

    def __post_init__(self) -> None:
        super().__post_init__()
        # Cast the basic joplin API datatypes to more convenient datatypes.
        if self.id is not None:
            self.id = int(self.id)

    @staticmethod
    def default_fields() -> set[str]:
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

    id: str | None = None
    type: LockType | None = None
    clientId: str | None = None
    clientType: LockClientType | None = None
    updatedTime: dt.datetime | None = None


@dataclass
class UserData(BaseData):
    """
    https://joplinapp.org/help/dev/spec/server_user_status/
    https://github.com/laurent22/joplin/blob/fc516d05b3c9564a54fd0fbb9a1886739190bba0/packages/server/src/services/database/types.ts#L246
    """

    id: str | None = None
    email: str | None = None
    password: str | None = None
    is_admin: bool | None = None
    full_name: str | None = None
    created_time: dt.datetime | None = None
    updated_time: dt.datetime | None = None
    email_confirmed: bool | None = None
    must_set_password: bool | None = None
    account_type: int | None = None  # TODO: enum
    can_upload: bool | None = None
    max_item_size: int | None = None
    max_total_item_size: int | None = None
    total_item_size: int | None = None
    can_share_folder: bool | None = None
    can_share_note: bool | None = None
    can_receive_folder: bool | None = None
    enabled: bool | None = None
    disabled_time: dt.datetime | None = None
    is_external: bool | None = None
    sso_auth_code: str | None = None
    sso_auth_code_expire_at: dt.datetime | None = None
    totp_secret: str | None = None


AnyData = (
    EventData
    | NoteData
    | NotebookData
    | NoteTagData
    | ResourceData
    | RevisionData
    | TagData
)


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
    cursor: int | None = None
    items: list[T] = field(default_factory=list)

    def __post_init__(self) -> None:
        # Cast the basic joplin API datatypes to more convenient datatypes.
        self.has_more = bool(self.has_more)
