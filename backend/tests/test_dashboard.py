from datetime import date, datetime

import pytest

from app.models import LeituraClima, MetricaTalhao, Praga, Talhao
from app.services import diagnostico as diag_svc
from tests.conftest import auth


@pytest.fixture
def fazenda(db):
    a = Talhao(
        nome="Grão 4.0",
        area_ha=10,
        cultura="Milho",
        sistema="AGRO_4_0",
        finalidade="GRAO",
        geometria="POLYGON((0 0, 1 0, 1 1, 0 1, 0 0))",
    )
    b = Talhao(nome="Grão Conv.", area_ha=12.5, cultura="Milho", sistema="CONVENCIONAL", finalidade="GRAO")
    praga = Praga(nome="Lagarta", limiar_alerta=1, limiar_controle=3, limiar_dano=6)
    db.add_all([a, b, praga])
    db.commit()
    db.add_all(
        [
            MetricaTalhao(talhao_id=a.id, data=date(2024, 1, 1), ndvi_medio=0.6),
            MetricaTalhao(talhao_id=a.id, data=date(2024, 1, 10), ndvi_medio=0.8),
            MetricaTalhao(talhao_id=b.id, data=date(2024, 1, 1), ndvi_medio=0.55),
            MetricaTalhao(talhao_id=b.id, data=date(2024, 1, 10), ndvi_medio=0.6),
            MetricaTalhao(talhao_id=a.id, data=date(2024, 3, 1), produtividade_kg_ha=11000),
            MetricaTalhao(talhao_id=b.id, data=date(2024, 3, 1), produtividade_kg_ha=9000),
            LeituraClima(data_hora=datetime(2024, 1, 5, 10), temp_med=25, chuva_mm=4),
        ]
    )
    db.commit()
    diag_svc.registrar_armadilha(db, b.id, praga.id, contagem=7, data=datetime(2024, 1, 5))  # ALTA
    diag_svc.registrar_armadilha(db, a.id, praga.id, contagem=2, data=datetime(2024, 1, 6))  # BAIXA
    return a, b


def test_resumo(client, agronomo_token, fazenda):
    a, b = fazenda
    r = client.get("/api/dashboard/resumo", headers=auth(agronomo_token))
    assert r.status_code == 200
    corpo = r.json()
    cards = corpo["cards"]
    assert cards["talhoes"] == 2
    assert cards["area_total_ha"] == 22.5
    assert cards["alertas_abertos"] == 1 and cards["alertas_altos"] == 1
    assert cards["diagnosticos"] == 2
    series = {s["talhao_id"]: s for s in corpo["ndvi_por_talhao"]}
    assert [p["ndvi"] for p in series[a.id]["serie"]] == [0.6, 0.8]
    mapa = {t["id"]: t for t in corpo["talhoes"]}
    assert mapa[b.id]["severidade"] == "ALTA"
    assert mapa[a.id]["severidade"] is None  # BAIXA não vira alerta
    assert mapa[a.id]["geometria"].startswith("POLYGON")
    assert mapa[a.id]["ultimo_ndvi"] == 0.8


def test_resumo_exige_login(client):
    assert client.get("/api/dashboard/resumo").status_code == 401


def test_comparativo(client, agronomo_token, fazenda):
    a, b = fazenda
    r = client.get(f"/api/comparativo?a={a.id}&b={b.id}", headers=auth(agronomo_token))
    assert r.status_code == 200
    c = r.json()
    assert c["a"]["talhao"]["nome"] == "Grão 4.0" and c["b"]["talhao"]["sistema"] == "CONVENCIONAL"
    assert [p["ndvi_medio"] for p in c["a"]["ndvi"]] == [0.6, 0.8]
    assert c["a"]["produtividade"][0]["produtividade_kg_ha"] == 11000
    assert c["b"]["pragas"][0]["contagem"] == 7
    assert c["a"]["indicadores"]["produtividade_kg_ha"] == 11000
    assert c["clima"][0]["chuva_mm"] == 4
    assert {e["talhao_id"] for e in c["eventos"]} == {a.id, b.id}


def test_comparativo_talhao_invalido_404(client, agronomo_token, fazenda):
    a, _ = fazenda
    assert client.get(f"/api/comparativo?a={a.id}&b=999", headers=auth(agronomo_token)).status_code == 404


def test_comparativo_sem_parametros_400(client, agronomo_token):
    assert client.get("/api/comparativo", headers=auth(agronomo_token)).status_code == 400
