import os
import re
import tempfile
from datetime import date

# Configure the app for tests before anything imports settings.
_tmpdir = tempfile.mkdtemp()
os.environ["DATABASE_URL"] = f"sqlite:///{_tmpdir}/test.db"
os.environ["JWT_SECRET"] = "test-secret-key-that-is-long-enough-for-hs256"
os.environ["COOKIE_SECURE"] = "false"
os.environ["STRIPE_WEBHOOK_SECRET"] = "whsec_test"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlmodel import Session, SQLModel  # noqa: E402

import app.models  # noqa: E402,F401
from app.core import security  # noqa: E402
from app.core.db import get_engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services.captcha import get_captcha_verifier  # noqa: E402
from app.services.email import get_email_sender  # noqa: E402
from app.services.llm import get_assistant_model  # noqa: E402

PASSWORD = "Sup3r-Secret-Pass!"


class FakeEmail:
    def __init__(self):
        self.sent: list[tuple[str, str, str]] = []

    def send(self, to, subject, body):
        self.sent.append((to, subject, body))

    def last_token(self) -> str:
        return re.search(r"token=(\S+)", self.sent[-1][2]).group(1)


class FakeCaptcha:
    def __init__(self):
        self.ok = True

    def verify(self, token, remote_ip):
        return self.ok


class FakeModel:
    def __init__(self):
        self.calls = []

    async def stream_reply(self, system, messages):
        self.calls.append((system, messages))
        for chunk in ("Try ", "lentil ", "soup."):
            yield chunk


@pytest.fixture(autouse=True)
def fast_hashing(monkeypatch):
    monkeypatch.setattr(security, "_SCRYPT_N", 2**10)


@pytest.fixture
def db():
    engine = get_engine()
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture
def fakes():
    email, captcha, model = FakeEmail(), FakeCaptcha(), FakeModel()
    app.dependency_overrides[get_email_sender] = lambda: email
    app.dependency_overrides[get_captcha_verifier] = lambda: captcha
    app.dependency_overrides[get_assistant_model] = lambda: model
    yield type("Fakes", (), {"email": email, "captcha": captcha, "model": model})
    app.dependency_overrides.clear()


@pytest.fixture
def client(db, fakes):
    with TestClient(app, base_url="http://testserver/api/v1") as c:
        yield c


def signup(client, email="ada@example.com", **overrides):
    body = {
        "first_name": "Ada",
        "last_name": "Lovelace",
        "email": email,
        "birthday": "1990-05-01",
        "password": PASSWORD,
        "password_confirm": PASSWORD,
        **overrides,
    }
    return client.post("/auth/signup", json=body)


@pytest.fixture
def auth(client, fakes):
    """A verified, signed-in user. Returns request headers."""
    assert signup(client).status_code == 201
    response = client.post("/auth/verify-email", json={"token": fakes.email.last_token()})
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def years_ago(n: int) -> str:
    today = date.today()
    return today.replace(year=today.year - n).isoformat()
