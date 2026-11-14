from datetime import UTC, datetime
from uuid import uuid4
from sqlalchemy import Boolean, Date, DateTime, ForeignKey, ForeignKeyConstraint, Index, Integer, String, Text, UniqueConstraint, text
from sqlalchemy.orm import Mapped, mapped_column as col
from .db import Base

def uid():
    return str(uuid4())

def now():
    return datetime.now(UTC).replace(tzinfo=None)

class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = col(String(36), primary_key=True, default=uid)
    name: Mapped[str] = col(String(120))
    timezone: Mapped[str] = col(String(80), default="UTC")
    external_ai_enabled: Mapped[bool] = col(Boolean, default=False)

class User(Base):
    __tablename__ = "agency_users"
    id: Mapped[str] = col(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = col(ForeignKey("workspaces.id", ondelete="CASCADE"), unique=True)
    email: Mapped[str] = col(String(254), unique=True)
    password_hash: Mapped[str] = col(Text)

class Project(Base):
    __tablename__ = "projects"
    id: Mapped[str] = col(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = col(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = col(String(120))
    target_launch_on = col(Date, nullable=True)
    archived_at = col(DateTime, nullable=True)
    created_at = col(DateTime, default=now, nullable=False)
    __table_args__ = (UniqueConstraint("workspace_id", "id"),)

class Item(Base):
    __tablename__ = "requests"
    id: Mapped[str] = col(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = col(String(36))
    project_id: Mapped[str] = col(String(36), index=True)
    title: Mapped[str] = col(String(120))
    instructions: Mapped[str] = col(Text)
    due_on = col(Date, nullable=True)
    status: Mapped[str] = col(String(24), default="awaiting_input")
    latest_revision_id = col(String(36), nullable=True)
    shared_revision_id = col(String(36), nullable=True)
    lock_version: Mapped[int] = col(Integer, default=0)
    cancelled_at = col(DateTime, nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], ondelete="CASCADE"),
        UniqueConstraint("workspace_id", "project_id", "id"),
    )

class Revision(Base):
    __tablename__ = "request_revisions"
    id: Mapped[str] = col(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = col(String(36))
    project_id: Mapped[str] = col(String(36))
    request_id: Mapped[str] = col(String(36), index=True)
    revision_no: Mapped[int] = col(Integer)
    source_role: Mapped[str] = col(String(8))
    body_text: Mapped[str] = col(Text)
    created_at = col(DateTime, default=now, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(["workspace_id", "project_id", "request_id"], ["requests.workspace_id", "requests.project_id", "requests.id"], ondelete="CASCADE"),
        UniqueConstraint("request_id", "revision_no"),
        UniqueConstraint("request_id", "id"),
    )

class Decision(Base):
    __tablename__ = "decisions"
    id: Mapped[str] = col(String(36), primary_key=True, default=uid)
    request_id: Mapped[str] = col(String(36))
    revision_id: Mapped[str] = col(String(36))
    review_cycle: Mapped[int] = col(Integer)
    decision: Mapped[str] = col(String(16))
    note = col(Text, nullable=True)
    guest_session_id: Mapped[str] = col(String(36))
    created_at = col(DateTime, default=now, nullable=False)
    __table_args__ = (
        ForeignKeyConstraint(["request_id", "revision_id"], ["request_revisions.request_id", "request_revisions.id"], ondelete="CASCADE"),
        UniqueConstraint("request_id", "review_cycle"),
    )

class Link(Base):
    __tablename__ = "review_links"
    id: Mapped[str] = col(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = col(String(36))
    project_id: Mapped[str] = col(String(36))
    token_hash: Mapped[str] = col(String(64), unique=True)
    expires_at = col(DateTime, nullable=False)
    revoked_at = col(DateTime, nullable=True)
    __table_args__ = (
        ForeignKeyConstraint(["workspace_id", "project_id"], ["projects.workspace_id", "projects.id"], ondelete="CASCADE"),
        Index("ix_single_active_link", "project_id", unique=True, postgresql_where=text("revoked_at IS NULL"), sqlite_where=text("revoked_at IS NULL")),
    )

class SessionRecord(Base):
    __tablename__ = "sessions"
    id: Mapped[str] = col(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = col(ForeignKey("workspaces.id", ondelete="CASCADE"))
    kind: Mapped[str] = col(String(8))
    user_id = col(ForeignKey("agency_users.id", ondelete="CASCADE"), nullable=True, index=True)
    link_id = col(ForeignKey("review_links.id", ondelete="CASCADE"), nullable=True)
    token_hash: Mapped[str] = col(String(64), unique=True)
    expires_at = col(DateTime, nullable=False)

class Event(Base):
    __tablename__ = "audit_events"
    id: Mapped[str] = col(String(36), primary_key=True, default=uid)
    workspace_id: Mapped[str] = col(ForeignKey("workspaces.id", ondelete="CASCADE"), index=True)
    project_id = col(String(36), nullable=True)
    request_id = col(String(36), nullable=True)
    event_type: Mapped[str] = col(String(40))
    actor_kind: Mapped[str] = col(String(8))
    created_at = col(DateTime, default=now, nullable=False)

class RateLimit(Base):
    __tablename__ = "rate_limits"
    scope: Mapped[str] = col(String(20), primary_key=True)
    key_hash: Mapped[str] = col(String(64), primary_key=True)
    window: Mapped[int] = col(Integer, primary_key=True)
    count: Mapped[int] = col(Integer)
