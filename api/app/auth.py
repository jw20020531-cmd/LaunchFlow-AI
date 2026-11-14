import hashlib
import os
import secrets
import time
from datetime import timedelta

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from .models import Link, Project, RateLimit, SessionRecord, User, now

ORIGIN = os.environ.get("APP_ORIGIN", "http://localhost:3000").rstrip("/")
SECURE = os.environ.get("SECURE_COOKIES") == "true"
if not SECURE and ORIGIN not in {"http://localhost:3000", "http://127.0.0.1:3000"}:
    raise RuntimeError("Non-local deployments require HTTPS and secure cookies")
if SECURE and not ORIGIN.startswith("https://"):
    raise RuntimeError("Secure cookies require an HTTPS APP_ORIGIN")
passwords = PasswordHasher()
dummy_hash = passwords.hash(secrets.token_urlsafe(32))

def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()

def check_password(encoded, password):
    try:
        return passwords.verify(encoded, password)
    except VerificationError:
        return False

def rate(db, scope, key, maximum, seconds=3600):
    window = int(time.time()) // seconds * seconds
    insert = sqlite_insert if db.bind.dialect.name == "sqlite" else pg_insert
    db.execute(delete(RateLimit).where(RateLimit.scope == scope, RateLimit.window < window - seconds))
    stmt = insert(RateLimit).values(scope=scope, key_hash=digest(key), window=window, count=1)
    count = db.execute(stmt.on_conflict_do_update(
        index_elements=["scope", "key_hash", "window"], set_={"count": RateLimit.count + 1}
    ).returning(RateLimit.count)).scalar_one()
    db.commit()
    if count > maximum:
        raise HTTPException(429, "Too many attempts. Try again later.")

def cookie_name(kind):
    return f"lf_{kind}"

def create_session(db, response, kind, workspace_id, *, user_id=None, link=None):
    raw = secrets.token_urlsafe(32)
    expires = now() + timedelta(hours=12 if kind == "owner" else 2)
    if link:
        expires = min(expires, link.expires_at)
    db.add(SessionRecord(kind=kind, workspace_id=workspace_id, user_id=user_id,
                         link_id=link.id if link else None, token_hash=digest(raw), expires_at=expires))
    db.commit()
    response.set_cookie(cookie_name(kind), raw, max_age=max(0, int((expires - now()).total_seconds())),
                        httponly=True, secure=SECURE, samesite="lax")

def principal(db, request, kind):
    token = request.cookies.get(cookie_name(kind), "")
    session = db.scalar(select(SessionRecord).where(
        SessionRecord.token_hash == digest(token), SessionRecord.kind == kind,
        SessionRecord.expires_at > now(),
    ))
    if not session:
        raise HTTPException(401, "Your session has expired.")
    if kind == "owner":
        owner = db.get(User, session.user_id)
        if not owner or owner.workspace_id != session.workspace_id:
            raise HTTPException(401, "Your session has expired.")
    return session

def guest_project(db, session, *, lock=False):
    link = db.get(Link, session.link_id)
    if not link or link.workspace_id != session.workspace_id:
        raise HTTPException(401, "This review link is unavailable.")
    query = select(Project).where(Project.id == link.project_id, Project.workspace_id == session.workspace_id)
    project = db.scalar(query.with_for_update() if lock else query)
    db.refresh(link)
    if not project or project.archived_at or link.revoked_at or link.expires_at <= now():
        raise HTTPException(401, "This review link is unavailable.")
    return project
