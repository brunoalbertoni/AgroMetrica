from tests.conftest import _criar_usuario, auth


def test_login_devolve_token_e_usuario(client, db):
    _criar_usuario(db, "a@a.com", "ADMIN")
    r = client.post("/api/auth/login", json={"email": "a@a.com", "senha": "senha123"})
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["access_token"]
    assert corpo["usuario"]["email"] == "a@a.com"
    assert corpo["usuario"]["perfil"] == "ADMIN"
    assert "senha_hash" not in corpo["usuario"]


def test_login_senha_errada_401(client, db):
    _criar_usuario(db, "a@a.com", "ADMIN")
    r = client.post("/api/auth/login", json={"email": "a@a.com", "senha": "errada"})
    assert r.status_code == 401
    assert r.json() == {"detail": "E-mail ou senha inválidos"}


def test_login_usuario_inativo_401(client, db):
    u = _criar_usuario(db, "a@a.com", "ADMIN")
    u.ativo = False
    db.commit()
    r = client.post("/api/auth/login", json={"email": "a@a.com", "senha": "senha123"})
    assert r.status_code == 401


def test_login_sem_campos_400(client):
    r = client.post("/api/auth/login", json={"email": "a@a.com"})
    assert r.status_code == 400
    assert isinstance(r.json()["detail"], str)


def test_me_sem_token_401(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_com_token(client, agronomo_token):
    r = client.get("/api/auth/me", headers=auth(agronomo_token))
    assert r.status_code == 200
    assert r.json()["perfil"] == "AGRONOMO"


def test_agronomo_recebe_403_em_usuarios(client, agronomo_token):
    assert client.get("/api/usuarios", headers=auth(agronomo_token)).status_code == 403


def test_admin_crud_usuarios(client, admin_token):
    h = auth(admin_token)
    r = client.post(
        "/api/usuarios",
        json={"nome": "Ana", "email": "ana@x.com", "senha": "segredo1", "perfil": "AGRONOMO"},
        headers=h,
    )
    assert r.status_code == 201, r.text
    uid = r.json()["id"]
    assert client.get("/api/usuarios", headers=h).json()[-1]["email"] == "ana@x.com"
    r = client.patch(f"/api/usuarios/{uid}", json={"nome": "Ana Maria", "ativo": False}, headers=h)
    assert r.status_code == 200 and r.json()["nome"] == "Ana Maria" and r.json()["ativo"] is False
    assert client.delete(f"/api/usuarios/{uid}", headers=h).status_code == 204
    assert client.get(f"/api/usuarios/{uid}", headers=h).status_code == 404


def test_email_duplicado_400(client, admin_token):
    h = auth(admin_token)
    body = {"nome": "X", "email": "admin@teste.com", "senha": "segredo1", "perfil": "ADMIN"}
    r = client.post("/api/usuarios", json=body, headers=h)
    assert r.status_code == 400
