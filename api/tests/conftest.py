import os
from pathlib import Path
import tempfile

import pytest

_temp = tempfile.TemporaryDirectory(prefix="launchflow-test-")
test_url = os.getenv("LAUNCHFLOW_TEST_DATABASE_URL")
if test_url:
    from sqlalchemy.engine import make_url
    if not (make_url(test_url).database or "").startswith("launchflow_test_"):
        raise RuntimeError("Use a disposable database prefixed launchflow_test_")
os.environ["DATABASE_URL"] = test_url or "sqlite:///" + Path(_temp.name, "test.sqlite3").as_posix()

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from app.auth import ORIGIN, passwords
from app.db import Session, engine
from app.main import app
from app.models import User, Workspace

PASSWORD = "test-only-password"

@pytest.fixture(scope="session", autouse=True)
def migrate():
    config = Config("alembic.ini")
    command.upgrade(config, "head")
    yield
    engine.dispose()

@pytest.fixture
def account():
    def add(email):
        with Session.begin() as db:
            w = Workspace(name=email)
            db.add(w)
            db.flush()
            db.add(User(workspace_id=w.id, email=email, password_hash=passwords.hash(PASSWORD)))
        return w.id
    return add

@pytest.fixture
def browser():
    clients = []
    def open_client():
        client = TestClient(app, headers={"Origin": ORIGIN})
        clients.append(client)
        return client
    yield open_client
    for client in clients:
        client.close()
