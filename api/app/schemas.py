from datetime import date
from typing import Annotated, Literal
from pydantic import BaseModel, ConfigDict, StringConstraints, Field

Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
Instructions = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
BodyText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=12000)]
Identifier = Annotated[str, StringConstraints(min_length=36, max_length=36)]

class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

class Login(Input):
    email: str = Field(min_length=3, max_length=254)
    password: str = Field(min_length=1, max_length=256)

class Password(Input):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)

class Logout(Input):
    scope: Literal["owner", "guest"]

class WorkspaceEdit(Input):
    name: Title | None = None
    timezone: str | None = Field(None, max_length=80)
    external_ai_enabled: bool | None = None

class ProjectCreate(Input):
    title: Title
    target_launch_on: date | None = None

class ProjectEdit(Input):
    title: Title | None = None
    target_launch_on: date | None = None
    archive: bool = False

class ItemCreate(Input):
    title: Title
    instructions: Instructions
    due_on: date | None = None

class Versioned(Input):
    lock_version: int = Field(ge=0)

class ItemEdit(Versioned):
    title: Title | None = None
    instructions: Instructions | None = None
    due_on: date | None = None
    cancel: bool = False

class RevisionIn(Versioned):
    body_text: BodyText

class ReviewIn(Versioned):
    action: Literal["share", "withdraw", "reopen"]
    revision_id: Identifier | None = None

class DecisionIn(Versioned):
    revision_id: Identifier
    decision: Literal["approve", "request_changes"]
    note: Annotated[str, StringConstraints(strip_whitespace=True, max_length=2000)] | None = None

class Exchange(Input):
    token: str = Field(min_length=43, max_length=43)

class Draft(Input):
    mode: Literal["manual", "preview", "ai"]
    confirmed: bool = False
    snapshot_digest: str | None = Field(None, min_length=64, max_length=64)
