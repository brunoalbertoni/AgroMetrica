from datetime import datetime, timedelta

import pytest
from sqlalchemy import select

from app.models import Alerta, LeituraClima, Praga, Prescricao, Produto, Talhao
from app.services import diagnostico as diag_svc
from app.services import prescricao as svc
from tests.conftest import auth

INICIO = datetime(2024, 2, 10, 0)


@pytest.fixture
def cenario(db):
    t = Talhao(nome="Grão 4.0", area_ha=10, cultura="Milho", sistema="AGRO_4_0", finalidade="GRAO")
    p = Praga(nome="Lagarta", limiar_alerta=2, limiar_controle=5, limiar_dano=10)
    prod = Produto(
        nome_comercial="Inseticida X", classe="INSETICIDA", dose_min=100, dose_max=200, unidade="mL/ha"
    )
    p.produtos.append(prod)
    db.add_all([t, p, prod])
    db.commit()
    return t, p, prod


def _hora(h, **kw):
    base = {"temp_med": 25, "temp_max": 26, "umidade_med": 70, "vento_kmh": 5, "chuva_mm": 0}
    return LeituraClima(data_hora=INICIO + timedelta(hours=h), **{**base, **kw})


def test_janela_respeita_condicoes(db):
    db.add_all(
        [
            _hora(0, vento_kmh=15),  # vento alto
            _hora(1, umidade_med=40),  # seco demais
            _hora(2, temp_max=32),  # quente demais
            _hora(3),  # boa, mas chove 2h depois (h5)
            _hora(4),  # boa, mas chove na hora seguinte
            _hora(5, chuva_mm=2),
            _hora(6),
            _hora(7),
            _hora(8),
            _hora(9),
            _hora(10, vento_kmh=12),
        ]
    )
    db.commit()
    inicio, fim = svc.encontrar_janela(db, INICIO)
    assert inicio == INICIO + timedelta(hours=6)
    assert fim == INICIO + timedelta(hours=10)  # fim da hora 9 (h7..h9 não têm chuva nas 2h seguintes)


def test_janela_inexistente(db):
    db.add_all([_hora(h, vento_kmh=20) for h in range(10)])
    db.commit()
    assert svc.encontrar_janela(db, INICIO) == (None, None)


def test_praga_alta_sugere_dose_media_e_gera_alerta(db, cenario):
    t, p, prod = cenario
    db.add_all([_hora(h) for h in range(12)])
    db.commit()
    diag = diag_svc.registrar_armadilha(db, t.id, p.id, contagem=11, data=INICIO)
    presc = db.scalars(select(Prescricao)).all()
    assert len(presc) == 1
    assert presc[0].dose == 150 and presc[0].unidade == "mL/ha"
    assert presc[0].status == "SUGERIDA"
    assert presc[0].janela_inicio == INICIO
    alerta = db.scalar(select(Alerta))
    assert alerta.severidade == "ALTA" and alerta.diagnostico_id == diag.id


def test_praga_baixa_nao_gera_alerta(db, cenario):
    t, p, _ = cenario
    diag_svc.registrar_armadilha(db, t.id, p.id, contagem=3, data=INICIO)
    assert db.scalar(select(Alerta)) is None


def test_contagem_abaixo_do_alerta_nao_gera_diagnostico(db, cenario):
    t, p, _ = cenario
    assert diag_svc.registrar_armadilha(db, t.id, p.id, contagem=1, data=INICIO) is None


def test_agronomo_aprova_prescricao(client, agronomo_token, db, cenario):
    t, p, _ = cenario
    diag_svc.registrar_armadilha(db, t.id, p.id, contagem=11, data=INICIO)
    presc = db.scalar(select(Prescricao))
    r = client.patch(
        f"/api/prescricoes/{presc.id}", json={"status": "APROVADA"}, headers=auth(agronomo_token)
    )
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "APROVADA"
    assert r.json()["aprovado_por"] is not None


def test_prescricao_status_invalido_400(client, agronomo_token, db, cenario):
    t, p, _ = cenario
    diag_svc.registrar_armadilha(db, t.id, p.id, contagem=11, data=INICIO)
    presc = db.scalar(select(Prescricao))
    r = client.patch(
        f"/api/prescricoes/{presc.id}", json={"status": "SUGERIDA"}, headers=auth(agronomo_token)
    )
    assert r.status_code == 400
    assert (
        client.patch(
            "/api/prescricoes/999", json={"status": "APROVADA"}, headers=auth(agronomo_token)
        ).status_code
        == 404
    )
