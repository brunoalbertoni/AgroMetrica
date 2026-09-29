import os
import tempfile
from pathlib import Path

_TMP = Path(tempfile.mkdtemp(prefix="agrometrica-test-"))
os.environ["DATABASE_URL"] = f"sqlite:///{(_TMP / 'test.db').as_posix()}"
os.environ["STORAGE_DIR"] = str(_TMP / "storage")
os.environ["JWT_SECRET"] = "segredo-de-teste"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.core.database import Base, SessionLocal, engine  # noqa: E402
from app.core.security import hash_senha  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Usuario  # noqa: E402


@pytest.fixture(autouse=True)
def _banco_limpo():
    Base.metadata.drop_all(engine)
    Base.metadata.create_all(engine)
    yield


@pytest.fixture
def db():
    sessao = SessionLocal()
    try:
        yield sessao
    finally:
        sessao.close()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def _criar_usuario(db, email, perfil):
    u = Usuario(
        nome=perfil.title(), email=email, senha_hash=hash_senha("senha123"), perfil=perfil, ativo=True
    )
    db.add(u)
    db.commit()
    return u


def _token(client, email):
    r = client.post("/api/auth/login", json={"email": email, "senha": "senha123"})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture
def admin_token(client, db):
    _criar_usuario(db, "admin@teste.com", "ADMIN")
    return _token(client, "admin@teste.com")


@pytest.fixture
def agronomo_token(client, db):
    _criar_usuario(db, "agro@teste.com", "AGRONOMO")
    return _token(client, "agro@teste.com")


def auth(token):
    return {"Authorization": f"Bearer {token}"}
