import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app          # noqa: E402
from app.db import get_db, init_db  # noqa: E402
from app.security import reset_rate_limits  # noqa: E402
from seed.seed import DEMO_EMAIL, DEMO_PASSWORD, seed_all  # noqa: E402

ADMIN_PW = "Admin#Test-123"


@pytest.fixture()
def app(tmp_path):
    app = create_app({"DATABASE": str(tmp_path / "t.db"), "TESTING": True, "SECRET_KEY": "test",
                      "ADMIN_EMAIL": "admin@navora.local"})
    with app.app_context():
        init_db()
        seed_all(get_db(), ADMIN_PW)
    reset_rate_limits()
    return app


@pytest.fixture()
def client(app):
    return app.test_client()


def token(client, path="/privacy"):
    html = client.get(path).get_data(as_text=True)
    return re.search(r'name="csrf-token" content="([^"]+)"', html).group(1)


def post(client, path, data=None, page="/privacy", **kw):
    data = dict(data or {})
    data["_csrf"] = token(client, page)
    return client.post(path, data=data, **kw)


def login(client, email, pw):
    return post(client, "/login", {"email": email, "password": pw})


@pytest.fixture()
def demo(client):
    r = login(client, DEMO_EMAIL, DEMO_PASSWORD)
    assert r.status_code == 302
    return client


@pytest.fixture()
def admin(client):
    r = login(client, "admin@navora.local", ADMIN_PW)
    assert r.status_code == 302
    return client


@pytest.fixture()
def student(client):
    """A fresh student who finished onboarding with a data-analyst goal."""
    post(client, "/register", {"name": "Asha Rao", "email": "asha@example.com", "password": "Str0ng-pass!"}, page="/register")
    return client

