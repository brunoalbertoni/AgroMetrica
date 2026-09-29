from datetime import date, datetime, timedelta

import pytest
from sqlalchemy import select

from app.core.config import settings
from app.models import Alerta, Diagnostico, LeituraClima, LeituraSolo, MetricaTalhao, Praga, Talhao
from app.services import diagnostico as svc
from tests.conftest import auth

REGRAS = settings.regras


@pytest.fixture
def praga():
    return Praga(nome="Lagarta", limiar_alerta=2, limiar_controle=5, limiar_dano=10)


@pytest.mark.parametrize(
    ("contagem", "esperado"),
    [(12, "ALTA"), (10, "ALTA"), (7, "MEDIA"), (5, "MEDIA"), (3, "BAIXA"), (2, "BAIXA"), (1, None)],
)
def test_regra_armadilha(praga, contagem, esperado):
    assert svc.classificar_praga(contagem, praga) == esperado


@pytest.mark.parametrize(
    ("anterior", "atual", "esperado"),
    [(0.80, 0.72, None), (0.80, 0.66, "MEDIA"), (0.80, 0.52, "ALTA"), (0.50, 0.60, None), (0, 0.3, None)],
)
def test_regra_queda_ndvi(anterior, atual, esperado):
    assert svc.avaliar_ndvi(anterior, atual, REGRAS) == esperado


@pytest.mark.parametrize(("balanco", "esperado"), [(-30, "MEDIA"), (-25, None), (-10, None), (None, None)])
def test_regra_balanco_hidrico(balanco, esperado):
    assert svc.avaliar_hidrico(balanco, REGRAS) == esperado


def test_limiares_vem_da_configuracao():
    regras = {**REGRAS, "ndvi": {"queda_media": 0.05, "queda_alta": 0.5}}
    assert svc.avaliar_ndvi(0.80, 0.74, regras) == "MEDIA"
    assert svc.avaliar_hidrico(-12, {**REGRAS, "hidrico": {"limite_mm": -10, "janela_dias": 7}}) == "MEDIA"


def _solo(**kw):
    base = {"ph": 6.0, "v_pct": 60, "p": 20, "k": 0.3}
    return LeituraSolo(ponto="P1", data_coleta=date(2024, 1, 1), **{**base, **kw})


@pytest.mark.parametrize(
    ("campos", "esperado"),
    [
        ({}, None),
        ({"ph": 4.8}, "BAIXA"),
        ({"v_pct": 45}, "BAIXA"),
        ({"k": 0.13}, "BAIXA"),
        ({"k": 0.10}, "MEDIA"),
        ({"p": 11}, "BAIXA"),
        ({"v_pct": 30}, "MEDIA"),  # abaixo de 80% do mínimo
        ({"ph": 3.9}, "MEDIA"),
    ],
)
def test_regra_nutricional(campos, esperado):
    severidade, problemas = svc.avaliar_solo(_solo(**campos), REGRAS)
    assert severidade == esperado
    assert bool(problemas) == (esperado is not None)


@pytest.fixture
def talhao(db):
    t = Talhao(nome="Grão 4.0", area_ha=10, cultura="Milho", sistema="AGRO_4_0", finalidade="GRAO")
    db.add(t)
    db.commit()
    return t


def test_rodar_gera_diagnosticos_e_alertas(db, talhao):
    db.add_all(
        [
            MetricaTalhao(talhao_id=talhao.id, data=date(2024, 2, 1), ndvi_medio=0.80),
            MetricaTalhao(talhao_id=talhao.id, data=date(2024, 2, 10), ndvi_medio=0.50),  # −37,5% → ALTA
            LeituraSolo(
                talhao_id=talhao.id, ponto="P1", data_coleta=date(2024, 1, 5), ph=4.8, v_pct=60, p=20, k=0.3
            ),
        ]
    )
    inicio = datetime(2024, 2, 4)
    for h in range(7 * 24):  # 7 dias sem chuva com ETP de 0,2 mm/h → −33,6 mm
        db.add(LeituraClima(data_hora=inicio + timedelta(hours=h), temp_med=25, chuva_mm=0, etp_mm=0.2))
    db.commit()

    criados = svc.rodar(db, talhao.id)
    tipos = {(d.tipo, d.severidade) for d in criados}
    assert ("VIGOR", "ALTA") in tipos
    assert ("HIDRICO", "MEDIA") in tipos
    assert ("NUTRICIONAL", "BAIXA") in tipos

    alertas = db.scalars(select(Alerta)).all()
    assert {a.severidade for a in alertas} == {"ALTA", "MEDIA"}  # BAIXA não gera alerta

    # rodar de novo não duplica
    assert svc.rodar(db, talhao.id) == []
    assert len(db.scalars(select(Diagnostico)).all()) == 3


def test_mensagens_usam_virgula_decimal(db, talhao):
    from app.services.alertas import mensagem

    vigor = Diagnostico(talhao_id=talhao.id, tipo="VIGOR", severidade="MEDIA", detalhes={"queda_pct": 20.0})
    hidrico = Diagnostico(
        talhao_id=talhao.id,
        tipo="HIDRICO",
        severidade="MEDIA",
        detalhes={"balanco_mm": -33.6, "janela_dias": 7},
    )
    assert mensagem(db, vigor) == "Queda de 20,0% no NDVI em Grão 4.0"
    assert mensagem(db, hidrico) == "Déficit hídrico de −33,6 mm em 7 dias em Grão 4.0"


def test_endpoint_rodar_exige_agronomo(client, admin_token, agronomo_token, talhao):
    r = client.post(f"/api/diagnosticos/rodar/{talhao.id}", headers=auth(agronomo_token))
    assert r.status_code == 200
    assert r.json() == []
    assert client.post("/api/diagnosticos/rodar/999", headers=auth(agronomo_token)).status_code == 404


def test_endpoint_rodar_sem_token_401(client, talhao):
    assert client.post(f"/api/diagnosticos/rodar/{talhao.id}").status_code == 401


def test_listar_e_detalhar_diagnostico(client, agronomo_token, db, talhao, praga):
    db.add(praga)
    db.commit()
    diag = svc.registrar_armadilha(
        db,
        talhao.id,
        praga.id,
        contagem=12,
        data=datetime(2024, 2, 10, 8),
        bboxes=[{"x": 0.1, "y": 0.2, "w": 0.05, "h": 0.05, "rotulo": "Lagarta", "confianca": 0.9}],
    )
    h = auth(agronomo_token)
    lista = client.get(f"/api/diagnosticos?talhao_id={talhao.id}&severidade=ALTA", headers=h).json()
    assert [d["id"] for d in lista] == [diag.id]
    assert client.get("/api/diagnosticos?severidade=BAIXA", headers=h).json() == []
    det = client.get(f"/api/diagnosticos/{diag.id}", headers=h).json()
    assert det["tipo"] == "PRAGA" and det["severidade"] == "ALTA"
    assert det["praga_nome"] == "Lagarta" and det["talhao_nome"] == "Grão 4.0"
    assert det["bboxes"][0]["x"] == 0.1
    assert det["prescricoes"] == []  # praga sem produto vinculado
    assert client.get("/api/diagnosticos/999", headers=h).status_code == 404
