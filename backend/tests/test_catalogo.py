from datetime import datetime

from app.models import Praga, Talhao
from app.services import diagnostico as diag_svc
from tests.conftest import auth

PRODUTO = {
    "nome_comercial": "Inseticida X",
    "ingrediente_ativo": "Clorantraniliprole",
    "classe": "INSETICIDA",
    "dose_min": 100,
    "dose_max": 150,
    "unidade": "mL/ha",
    "carencia_dias": 30,
    "registro_mapa": "1234",
}


def test_crud_produtos_admin(client, admin_token, db):
    h = auth(admin_token)
    praga = Praga(nome="Lagarta", limiar_alerta=1, limiar_controle=2, limiar_dano=3)
    db.add(praga)
    db.commit()
    r = client.post("/api/produtos", json={**PRODUTO, "praga_ids": [praga.id]}, headers=h)
    assert r.status_code == 201, r.text
    pid = r.json()["id"]
    assert r.json()["praga_ids"] == [praga.id]
    assert client.get("/api/produtos", headers=h).json()[0]["nome_comercial"] == "Inseticida X"
    r = client.patch(f"/api/produtos/{pid}", json={"dose_max": 180, "praga_ids": []}, headers=h)
    assert r.json()["dose_max"] == 180 and r.json()["praga_ids"] == []
    assert client.delete(f"/api/produtos/{pid}", headers=h).status_code == 204
    assert client.get(f"/api/produtos/{pid}", headers=h).status_code == 404


def test_produto_dose_min_maior_que_max_400(client, admin_token):
    r = client.post("/api/produtos", json={**PRODUTO, "dose_min": 200}, headers=auth(admin_token))
    assert r.status_code == 400


def test_agronomo_le_mas_nao_escreve_catalogo(client, agronomo_token):
    h = auth(agronomo_token)
    assert client.get("/api/produtos", headers=h).status_code == 200
    assert client.get("/api/pragas", headers=h).status_code == 200
    assert client.post("/api/produtos", json=PRODUTO, headers=h).status_code == 403
    praga = {"nome": "P", "limiar_alerta": 1, "limiar_controle": 2, "limiar_dano": 3}
    assert client.post("/api/pragas", json=praga, headers=h).status_code == 403


def test_crud_pragas_admin(client, admin_token):
    h = auth(admin_token)
    body = {
        "nome": "Percevejo",
        "nome_cientifico": "Euschistus heros",
        "cultura": "Soja",
        "limiar_alerta": 1,
        "limiar_controle": 2,
        "limiar_dano": 4,
    }
    r = client.post("/api/pragas", json=body, headers=h)
    assert r.status_code == 201
    pid = r.json()["id"]
    assert client.patch(f"/api/pragas/{pid}", json={"limiar_dano": 5}, headers=h).json()["limiar_dano"] == 5
    assert client.delete(f"/api/pragas/{pid}", headers=h).status_code == 204


def test_limiares_de_praga_fora_de_ordem_400(client, admin_token):
    body = {"nome": "X", "limiar_alerta": 5, "limiar_controle": 2, "limiar_dano": 4}
    assert client.post("/api/pragas", json=body, headers=auth(admin_token)).status_code == 400


def test_alertas_listar_e_marcar_lido(client, agronomo_token, db):
    t = Talhao(nome="T", area_ha=1, cultura="Milho", sistema="AGRO_4_0", finalidade="GRAO")
    p = Praga(nome="Lagarta", limiar_alerta=1, limiar_controle=2, limiar_dano=3)
    db.add_all([t, p])
    db.commit()
    diag = diag_svc.registrar_armadilha(db, t.id, p.id, contagem=5, data=datetime(2024, 1, 1))
    h = auth(agronomo_token)
    alertas = client.get("/api/alertas?lido=false", headers=h).json()
    assert len(alertas) == 1
    assert alertas[0]["diagnostico_id"] == diag.id and alertas[0]["talhao_id"] == t.id
    assert alertas[0]["severidade"] == "ALTA"
    r = client.patch(f"/api/alertas/{alertas[0]['id']}/lido", headers=h)
    assert r.status_code == 200 and r.json()["lido"] is True
    assert client.get("/api/alertas?lido=false", headers=h).json() == []
    assert len(client.get("/api/alertas?lido=true", headers=h).json()) == 1
