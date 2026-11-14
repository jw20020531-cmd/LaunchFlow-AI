from datetime import UTC, datetime, timedelta
import json
import secrets
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import httpx
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import delete, func, select, text, update

from . import ai, schemas as s
from .auth import ORIGIN, check_password, cookie_name, create_session, digest, dummy_hash, guest_project, passwords, principal, rate
from .db import database
from .models import Decision, Event, Item, Link, Project, Revision, SessionRecord, User, Workspace, now

app = FastAPI(title="LaunchFlow AI", docs_url=None, redoc_url=None, openapi_url=None)
api = APIRouter(prefix="/api/v1")
DB = Depends(database)

def error(request, status, message):
    return JSONResponse({"error": {"code": status, "message": message, "request_id": request.state.request_id}}, status)

@app.middleware("http")
async def protect(request: Request, call_next):
    request.state.request_id = str(uuid4())
    if request.method not in {"GET", "HEAD", "OPTIONS"}:
        if request.headers.get("origin") != ORIGIN:
            return error(request, 403, "Request origin is not allowed.")
        length = request.headers.get("content-length", "")
        if length and (not length.isdecimal() or int(length) > 65536):
            return error(request, 413, "Request exceeds 64 KiB.")
        # Cache on this middleware's request so Starlette can replay it.
        if request.headers.get("transfer-encoding") or (not length and request.headers.get("content-type")):
            return error(request, 411, "Provide a content length.")
        body = await request.body()
        if len(body) > 65536:
            return error(request, 413, "Request exceeds 64 KiB.")
        if body and request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
            return error(request, 415, "Expected JSON.")
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Request-ID"] = request.state.request_id
    return response

@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return error(request, exc.status_code, exc.detail)

@app.exception_handler(RequestValidationError)
async def invalid(request, exc):
    fields = ", ".join(".".join(map(str, e["loc"][1:])) for e in exc.errors())
    return error(request, 422, f"Check the submitted fields: {fields or 'input'}.")

def data(value, fields):
    return {field: getattr(value, field) for field in fields.split()}

def stamp(dt):
    return dt.replace(tzinfo=UTC).isoformat() if dt else None

def owner(request, db):
    return principal(db, request, "owner")

def selected_project(db, session, project_id, *, write=False):
    query = select(Project).where(Project.id == str(project_id), Project.workspace_id == session.workspace_id)
    project = db.scalar(query.with_for_update() if write else query)
    if not project:
        raise HTTPException(404, "Project unavailable.")
    if write and project.archived_at:
        raise HTTPException(409, "Archived projects are read-only.")
    return project

def item_query(project):
    return select(Item).where(Item.project_id == project.id, Item.workspace_id == project.workspace_id)

def selected_item(db, project, item_id, version=None):
    query = item_query(project).where(Item.id == str(item_id))
    item = db.scalar(query.with_for_update() if version is not None else query)
    if not item or item.cancelled_at:
        raise HTTPException(404, "Request unavailable.")
    if version is not None and item.lock_version != version:
        raise HTTPException(409, "This request changed. Reload and try again.")
    return item

def event(db, project, kind, item=None, role="owner"):
    db.add(Event(workspace_id=project.workspace_id, project_id=project.id,
                 request_id=item.id if item else None, event_type=kind, actor_kind=role))

def today(db, workspace_id):
    return datetime.now(ZoneInfo(db.get(Workspace, workspace_id).timezone)).date()

def states(db, project):
    return db.scalars(item_query(project).where(Item.cancelled_at.is_(None)).order_by(Item.id)).all()

def counts(items, current_date):
    total = len(items)
    approved = sum(i.status == "approved" for i in items)
    overdue = sum(bool(i.due_on and i.due_on < current_date and i.status != "approved") for i in items)
    return {"total": total, "approved": approved, "overdue": overdue, "ready": bool(total and total == approved)}

def project_view(db, project):
    return {**data(project, "id title target_launch_on"), "archived_at": stamp(project.archived_at),
            **counts(states(db, project), today(db, project.workspace_id))}

def revision_view(revision):
    return {**data(revision, "id revision_no source_role body_text"), "created_at": stamp(revision.created_at)}

def item_view(db, item, current_date, *, guest=False):
    result = data(item, "id title instructions due_on status lock_version shared_revision_id")
    result["overdue"] = bool(item.due_on and item.due_on < current_date and item.status != "approved")
    if guest:
        revision = db.get(Revision, item.shared_revision_id) if item.status in {"in_review", "approved", "changes_requested"} and item.shared_revision_id else None
        if not revision and item.status in {"submitted", "changes_requested"}:
            revision = db.scalar(select(Revision).where(Revision.request_id == item.id, Revision.source_role == "guest").order_by(Revision.revision_no.desc()).limit(1))
    else:
        revision = db.get(Revision, item.latest_revision_id) if item.latest_revision_id else None
        result.update(latest_revision_id=item.latest_revision_id, cancelled_at=stamp(item.cancelled_at))
    result["revision"] = revision_view(revision) if revision else None
    return result

def page(db, query, model, cursor, limit):
    if cursor:
        query = query.where(model.id > str(cursor))
    rows = db.scalars(query.order_by(model.id).limit(limit + 1)).all()
    return rows[:limit], rows[limit-1].id if len(rows) > limit else None

def revoke_links(db, project):
    db.execute(update(Link).where(Link.project_id == project.id, Link.revoked_at.is_(None)).values(revoked_at=now()))

def ensure(condition, message="This action is unavailable in the current state."):
    if not condition:
        raise HTTPException(409, message)

def add_revision(db, item, body, role):
    revision_no = db.scalar(select(func.max(Revision.revision_no)).where(Revision.request_id == item.id)) or 0
    revision = Revision(workspace_id=item.workspace_id, project_id=item.project_id, request_id=item.id,
                        revision_no=revision_no + 1, source_role=role, body_text=body)
    db.add(revision)
    db.flush()
    item.latest_revision_id = revision.id
    item.shared_revision_id = None
    item.status = "submitted"
    item.lock_version += 1
    return revision

@api.get("/health/live")
def live():
    return {"status": "ok"}

@api.get("/health/ready")
def ready(db=DB):
    db.execute(text("SELECT 1"))
    return {"status": "ok"}

@api.post("/auth/login")
def login(body: s.Login, request: Request, response: Response, db=DB):
    # Shared proxy bucket complements the per-account limit.
    rate(db, "login_global", "installation", 120, 900)
    email = body.email.strip().lower()
    rate(db, "login_account", email, 10, 900)
    user = db.scalar(select(User).where(User.email == email))
    if not check_password(user.password_hash if user else dummy_hash, body.password) or not user:
        raise HTTPException(401, "Email or password is incorrect.")
    create_session(db, response, "owner", user.workspace_id, user_id=user.id)
    return workspace_view(db, user.workspace_id)

@api.post("/auth/logout", status_code=204)
def logout(body: s.Logout, request: Request, response: Response, db=DB):
    token = request.cookies.get(cookie_name(body.scope), "")
    db.execute(delete(SessionRecord).where(SessionRecord.token_hash == digest(token), SessionRecord.kind == body.scope))
    db.commit()
    response.delete_cookie(cookie_name(body.scope))

@api.post("/auth/password", status_code=204)
def change_password(body: s.Password, request: Request, response: Response, db=DB):
    session = owner(request, db)
    user_id = session.user_id
    rate(db, "password", user_id, 10)
    user = db.scalar(select(User).where(User.id == user_id).with_for_update())
    if not check_password(user.password_hash, body.current_password):
        raise HTTPException(401, "Current password is incorrect.")
    user.password_hash = passwords.hash(body.new_password)
    db.execute(delete(SessionRecord).where(SessionRecord.user_id == user.id))
    db.commit()
    response.delete_cookie(cookie_name("owner"))

def workspace_view(db, workspace_id):
    return {**data(db.get(Workspace, workspace_id), "id name timezone external_ai_enabled"),
            "ai_available": ai.configured_provider() is not None}

@api.get("/auth/me")
def me(request: Request, db=DB):
    return workspace_view(db, owner(request, db).workspace_id)

@api.patch("/workspace")
def workspace(body: s.WorkspaceEdit, request: Request, db=DB):
    w = db.get(Workspace, owner(request, db).workspace_id)
    if body.timezone is not None:
        try:
            ZoneInfo(body.timezone)
        except (ZoneInfoNotFoundError, ValueError):
            raise HTTPException(422, "Use a valid IANA time zone.") from None
        w.timezone = body.timezone
    if body.name:
        w.name = body.name
    if body.external_ai_enabled is not None:
        ensure(not body.external_ai_enabled or ai.configured_provider(), "No AI provider is configured.")
        w.external_ai_enabled = body.external_ai_enabled
    db.commit()
    return workspace_view(db, w.id)

@api.get("/projects")
def list_projects(request: Request, archived: bool = False, limit: int = Query(25, ge=1, le=100), cursor: UUID | None = None, db=DB):
    session = owner(request, db)
    query = select(Project).where(Project.workspace_id == session.workspace_id,
                                  Project.archived_at.is_not(None) if archived else Project.archived_at.is_(None))
    rows, next_cursor = page(db, query, Project, cursor, limit)
    return {"items": [project_view(db, x) for x in rows], "next_cursor": next_cursor}

@api.post("/projects", status_code=201)
def create_project(body: s.ProjectCreate, request: Request, db=DB):
    project = Project(workspace_id=owner(request, db).workspace_id, **body.model_dump())
    db.add(project)
    db.flush()
    event(db, project, "project_created")
    db.commit()
    return project_view(db, project)

@api.get("/projects/{p}")
def get_project(p: UUID, request: Request, db=DB):
    return project_view(db, selected_project(db, owner(request, db), p))

@api.patch("/projects/{p}")
def edit_project(p: UUID, body: s.ProjectEdit, request: Request, db=DB):
    project = selected_project(db, owner(request, db), p, write=True)
    if body.title is not None:
        project.title = body.title
    if "target_launch_on" in body.model_fields_set:
        project.target_launch_on = body.target_launch_on
    if body.archive:
        project.archived_at = now()
        revoke_links(db, project)
    event(db, project, "project_archived" if body.archive else "project_edited")
    db.commit()
    return project_view(db, project)

@api.get("/projects/{p}/requests")
def list_items(p: UUID, request: Request, limit: int = Query(25, ge=1, le=100), cursor: UUID | None = None, db=DB):
    project = selected_project(db, owner(request, db), p)
    rows, next_cursor = page(db, item_query(project), Item, cursor, limit)
    current = today(db, project.workspace_id)
    return {"items": [item_view(db, i, current) for i in rows], "next_cursor": next_cursor}

@api.post("/projects/{p}/requests", status_code=201)
def create_item(p: UUID, body: s.ItemCreate, request: Request, db=DB):
    project = selected_project(db, owner(request, db), p, write=True)
    item = Item(project_id=project.id, workspace_id=project.workspace_id, **body.model_dump())
    db.add(item)
    db.flush()
    event(db, project, "request_created", item)
    db.commit()
    return item_view(db, item, today(db, project.workspace_id))

@api.patch("/projects/{p}/requests/{r}")
def edit_item(p: UUID, r: UUID, body: s.ItemEdit, request: Request, db=DB):
    project = selected_project(db, owner(request, db), p, write=True)
    item = selected_item(db, project, r, body.lock_version)
    ensure(item.status != "in_review", "Withdraw the review before changing the request.")
    for key in ("title", "instructions"):
        if getattr(body, key) is not None:
            setattr(item, key, getattr(body, key))
    if "due_on" in body.model_fields_set:
        item.due_on = body.due_on
    if body.cancel:
        item.cancelled_at = now()
    item.lock_version += 1
    event(db, project, "request_cancelled" if body.cancel else "request_edited", item)
    db.commit()
    return item_view(db, item, today(db, project.workspace_id))

@api.get("/projects/{p}/requests/{r}/history")
def history(p: UUID, r: UUID, request: Request, limit: int = Query(25, ge=1, le=100),
            cursor: UUID | None = None, db=DB):
    project = selected_project(db, owner(request, db), p)
    item = db.scalar(item_query(project).where(Item.id == str(r)))
    if not item:
        raise HTTPException(404, "Request unavailable.")
    rows, next_cursor = page(db, select(Revision).where(Revision.request_id == item.id), Revision, cursor, limit)
    ids = [revision.id for revision in rows]
    decisions = db.scalars(select(Decision).where(Decision.request_id == item.id, Decision.revision_id.in_(ids)).order_by(Decision.review_cycle)).all()
    return {"revisions": [revision_view(x) for x in rows], "next_cursor": next_cursor,
            "decisions": [{**data(x, "revision_id review_cycle decision note"), "created_at": stamp(x.created_at)} for x in decisions]}

@api.post("/projects/{p}/requests/{r}/revisions", status_code=201)
def create_revision(p: UUID, r: UUID, body: s.RevisionIn, request: Request, db=DB):
    project = selected_project(db, owner(request, db), p, write=True)
    item = selected_item(db, project, r, body.lock_version)
    ensure(item.status in {"submitted", "changes_requested"})
    revision = add_revision(db, item, body.body_text, "owner")
    event(db, project, "revision_saved", item)
    db.commit()
    return {"revision": revision_view(revision), "request": item_view(db, item, today(db, project.workspace_id))}

@api.post("/projects/{p}/requests/{r}/review")
def set_review(p: UUID, r: UUID, body: s.ReviewIn, request: Request, db=DB):
    project = selected_project(db, owner(request, db), p, write=True)
    item = selected_item(db, project, r, body.lock_version)
    if body.action == "share":
        ensure(item.status in {"submitted", "changes_requested"} and body.revision_id and body.revision_id == item.latest_revision_id)
        item.shared_revision_id = body.revision_id
        item.status = "in_review"
    else:
        ensure(item.status == ("approved" if body.action == "reopen" else "in_review"))
        item.shared_revision_id = None
        item.status = "submitted"
    item.lock_version += 1
    event(db, project, f"review_{body.action}", item)
    db.commit()
    return item_view(db, item, today(db, project.workspace_id))

@api.post("/projects/{p}/link", status_code=201)
def issue_link(p: UUID, request: Request, db=DB):
    project = selected_project(db, owner(request, db), p, write=True)
    revoke_links(db, project)
    raw = secrets.token_urlsafe(32)
    link = Link(workspace_id=project.workspace_id, project_id=project.id,
                token_hash=digest(raw), expires_at=now()+timedelta(days=14))
    db.add(link)
    event(db, project, "link_issued")
    db.commit()
    return {"url": f"{ORIGIN}/r#token={raw}", "expires_at": stamp(link.expires_at)}

@api.delete("/projects/{p}/link", status_code=204)
def revoke_link(p: UUID, request: Request, db=DB):
    project = selected_project(db, owner(request, db), p, write=True)
    revoke_links(db, project)
    event(db, project, "link_revoked")
    db.commit()

@api.post("/guest/exchange")
def exchange(body: s.Exchange, response: Response, db=DB):
    rate(db, "guest_exchange", "installation", 200, 900)
    link = db.scalar(select(Link).where(Link.token_hash == digest(body.token)))
    if not link or link.revoked_at or link.expires_at <= now():
        raise HTTPException(404, "This review link is unavailable.")
    project = db.get(Project, link.project_id)
    if not project or project.archived_at:
        raise HTTPException(404, "This review link is unavailable.")
    create_session(db, response, "guest", link.workspace_id, link=link)
    return {"title": project.title}

@api.get("/guest/project")
def get_guest_project(request: Request, db=DB):
    project = guest_project(db, principal(db, request, "guest"))
    return {"title": project.title, **counts(states(db, project), today(db, project.workspace_id))}

@api.get("/guest/requests")
def guest_items(request: Request, limit: int = Query(25, ge=1, le=100), cursor: UUID | None = None, db=DB):
    project = guest_project(db, principal(db, request, "guest"))
    rows, next_cursor = page(db, item_query(project).where(Item.cancelled_at.is_(None)), Item, cursor, limit)
    current = today(db, project.workspace_id)
    return {"items": [item_view(db, i, current, guest=True) for i in rows], "next_cursor": next_cursor}

@api.post("/guest/requests/{r}/submit", status_code=201)
def submit(r: UUID, body: s.RevisionIn, request: Request, db=DB):
    session = principal(db, request, "guest")
    rate(db, "guest_write", session.link_id, 120)
    project = guest_project(db, session, lock=True)
    item = selected_item(db, project, r, body.lock_version)
    ensure(item.status in {"awaiting_input", "submitted", "changes_requested"})
    add_revision(db, item, body.body_text, "guest")
    event(db, project, "client_submitted", item, "guest")
    db.commit()
    return item_view(db, item, today(db, project.workspace_id), guest=True)

@api.post("/guest/requests/{r}/decision", status_code=201)
def decide(r: UUID, body: s.DecisionIn, request: Request, db=DB):
    session = principal(db, request, "guest")
    rate(db, "guest_write", session.link_id, 120)
    project = guest_project(db, session, lock=True)
    item = selected_item(db, project, r, body.lock_version)
    ensure(item.status == "in_review" and item.shared_revision_id == body.revision_id)
    if body.decision == "request_changes" and not body.note:
        raise HTTPException(422, "Add a note explaining what should change.")
    db.add(Decision(request_id=item.id, revision_id=item.shared_revision_id, review_cycle=item.lock_version,
                    decision=body.decision, note=body.note, guest_session_id=session.id))
    item.status = "approved" if body.decision == "approve" else "changes_requested"
    item.lock_version += 1
    event(db, project, item.status, item, "guest")
    db.commit()
    return item_view(db, item, today(db, project.workspace_id), guest=True)

@api.post("/projects/{p}/status-drafts")
def status_draft(p: UUID, body: s.Draft, request: Request, db=DB):
    project = selected_project(db, owner(request, db), p)
    items = states(db, project)
    summary = {"counts": counts(items, today(db, project.workspace_id)),
               "items": [{"title": i.title, "status": i.status, "due_on": str(i.due_on) if i.due_on else None} for i in items[:50]]}
    snapshot_digest = digest(json.dumps(summary, sort_keys=True))
    result = ai.manual(summary)
    if body.mode in {"preview", "ai"}:
        provider = ai.configured_provider()
        if not provider or not db.get(Workspace, project.workspace_id).external_ai_enabled:
            raise HTTPException(503, "AI is unavailable. Use the manual draft.")
    if body.mode == "ai":
        if not body.confirmed:
            raise HTTPException(422, "Confirm the fields before requesting AI.")
        ensure(body.snapshot_digest == snapshot_digest, "The checklist changed. Load a fresh AI preview.")
        rate(db, "ai", project.workspace_id, 10)
        try:
            result = provider.draft(summary)
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError):
            raise HTTPException(503, "AI is unavailable. Use the manual draft.") from None
    return {"text": result, "snapshot_at": stamp(now()), "snapshot": summary, "snapshot_digest": snapshot_digest,
            "source_request_ids": [i.id for i in items[:50]]}

@api.get("/workspace/export")
def export_workspace(request: Request, db=DB):
    w = db.get(Workspace, owner(request, db).workspace_id)
    projects = db.scalars(select(Project).where(Project.workspace_id == w.id)).all()
    archive = []
    for p in projects:
        entries = []
        for item in db.scalars(item_query(p)):
            revisions = db.scalars(select(Revision).where(Revision.request_id == item.id)).all()
            decisions = db.scalars(select(Decision).where(Decision.request_id == item.id)).all()
            entries.append({**item_view(db, item, today(db, w.id)), "revisions": [revision_view(r) for r in revisions],
                            "decisions": [{**data(d, "revision_id decision note"), "created_at": stamp(d.created_at)} for d in decisions]})
        archive.append({**project_view(db, p), "requests": entries})
    audit = db.scalars(select(Event).where(Event.workspace_id == w.id).order_by(Event.created_at)).all()
    return Response(json.dumps({"workspace": data(w, "id name timezone"), "projects": archive,
                                "audit": [{**data(e, "project_id request_id event_type actor_kind"), "created_at": stamp(e.created_at)} for e in audit]}, default=str),
                    media_type="application/json", headers={"Content-Disposition": 'attachment; filename="launchflow-export.json"'})

app.include_router(api)
