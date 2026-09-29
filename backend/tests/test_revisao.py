"""Regressões apontadas na revisão final do branch."""

from datetime import datetime

from sqlalchemy import func, select

from app.core.config import Settings
from app.models import LeituraClima, LeituraSolo, Praga, Prescricao, Produto, Talhao, Upload
from app.services import diagnostico as diag_svc
from tests.conftest import auth


def _cenario(db):
    t = Talhao(nome="T1", area_ha=1, cultura="Milho", sistema="AGRO_4_0", finalidade="GRAO")
    p = Praga(nome="Lagarta", limiar_alerta=1, limiar_controle=2, limiar_dano=3)
    prod = Produto(nome_comercial="X", classe="INSETICIDA", dose_min=1, dose_max=2, unidade="L/ha")
    p.produtos.append(prod)
    db.add_all([t, p, prod])
    db.commit()
    return t, p, prod


def test_upload_de_html_como_imagem_e_recusado(client, agronomo_token, db):
    t, _, _ = _cenario(db)
    r = client.post(
        "/api/imagens",
        data={"talhao_id": str(t.id), "tipo": "FOLHA"},
        files={"arquivo": ("x.html", b"<script>alert(1)</script>", "text/html")},
        headers=auth(agronomo_token),
    )
    assert r.status_code == 400
    assert "formato" in r.json()["detail"].lower()


def test_arquivos_servidos_com_nosniff(client, agronomo_token, db, tmp_path):
    import cv2
    import numpy as np

    t, _, _ = _cenario(db)
    ok, png = cv2.imencode(".png", np.zeros((4, 4, 3), dtype=np.uint8))
    r = client.post(
        "/api/imagens",
        data={"talhao_id": str(t.id), "tipo": "FOLHA"},
        files={"arquivo": ("f.png", png.tobytes(), "image/png")},
        headers=auth(agronomo_token),
    )
    resp = client.get(r.json()["url"])
    assert resp.headers.get("x-content-type-options") == "nosniff"


def test_excluir_praga_com_diagnostico_devolve_409(client, admin_token, db):
    t, p, _ = _cenario(db)
    diag_svc.registrar_armadilha(db, t.id, p.id, contagem=5, data=datetime(2024, 1, 1))
    r = client.delete(f"/api/pragas/{p.id}", headers=auth(admin_token))
    assert r.status_code == 409
    assert isinstance(r.json()["detail"], str)


def test_excluir_produto_com_prescricao_devolve_409(client, admin_token, db):
    t, p, prod = _cenario(db)
    diag_svc.registrar_armadilha(db, t.id, p.id, contagem=5, data=datetime(2024, 1, 1))
    r = client.delete(f"/api/produtos/{prod.id}", headers=auth(admin_token))
    assert r.status_code == 409


def test_excluir_usuario_com_historico_devolve_409(client, admin_token, agronomo_token, db):
    _cenario(db)
    client.post(
        "/api/uploads/clima",
        files={"arquivo": ("c.csv", b"Data;temp_med;chuva\n01/01/2024 10:00;20;0\n", "text/csv")},
        headers=auth(agronomo_token),
    )
    uid = client.get("/api/auth/me", headers=auth(agronomo_token)).json()["id"]
    r = client.delete(f"/api/usuarios/{uid}", headers=auth(admin_token))
    assert r.status_code == 409


def test_armadilha_com_data_com_fuso_gera_prescricao(client, agronomo_token, db):
    t, p, _ = _cenario(db)
    base = {"temp_med": 25, "temp_max": 26, "umidade_med": 70, "vento_kmh": 5, "chuva_mm": 0}
    db.add_all([LeituraClima(data_hora=datetime(2024, 1, 10, h), **base) for h in range(8, 14)])
    db.commit()
    r = client.post(
        "/api/diagnosticos/armadilha",
        json={"talhao_id": t.id, "praga_id": p.id, "contagem": 5, "data": "2024-01-10T08:00:00Z"},
        headers=auth(agronomo_token),
    )
    assert r.status_code == 200, r.text
    assert db.scalar(select(func.count()).select_from(Prescricao)) == 1


def test_segredo_jwt_padrao_e_substituido():
    s = Settings(jwt_secret="troque-isto")
    assert s.jwt_secret != "troque-isto"
    assert len(s.jwt_secret) >= 32
    assert Settings(jwt_secret="meu-segredo-forte").jwt_secret == "meu-segredo-forte"


def test_valor_longo_vira_erro_de_linha_sem_derrubar_lote(client, agronomo_token, db):
    t, _, _ = _cenario(db)
    ponto_longo = "P" * 60
    csv = f"talhao_id;ponto;data_coleta;ph\n{t.id};P1;10/01/2024;5,5\n{t.id};{ponto_longo};10/01/2024;5,6\n"
    r = client.post(
        "/api/uploads/solo",
        files={"arquivo": ("solo.csv", csv.encode(), "text/csv")},
        headers=auth(agronomo_token),
    )
    assert r.status_code == 200
    assert r.json()["linhas_ok"] == 1 and r.json()["linhas_erro"] == 1
    assert db.scalar(select(func.count()).select_from(LeituraSolo)) == 1


def test_nome_de_arquivo_longo_nao_quebra_upload(client, agronomo_token, db):
    nome = "a" * 300 + ".csv"
    r = client.post(
        "/api/uploads/clima",
        files={"arquivo": (nome, b"Data;temp_med;chuva\n01/01/2024 10:00;20;0\n", "text/csv")},
        headers=auth(agronomo_token),
    )
    assert r.status_code == 200
    assert len(db.scalar(select(Upload.nome_arquivo))) <= 255
