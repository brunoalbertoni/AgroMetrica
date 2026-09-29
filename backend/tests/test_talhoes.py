from datetime import date, datetime

import pytest

from app.models import LeituraClima, LeituraSolo, MetricaTalhao, Talhao
from tests.conftest import auth


@pytest.fixture
def talhoes(db):
    dados = [
        ("Grão 4.0", "AGRO_4_0", "GRAO", 12.5),
        ("Grão Convencional", "CONVENCIONAL", "GRAO", 11.0),
        ("Silagem 4.0", "AGRO_4_0", "SILAGEM", 8.2),
        ("Silagem Convencional", "CONVENCIONAL", "SILAGEM", 7.9),
    ]
    objs = [Talhao(nome=n, sistema=s, finalidade=f, area_ha=a, cultura="Milho") for n, s, f, a in dados]
    db.add_all(objs)
    db.commit()
    # balanço hídrico mais recente: -30 no primeiro, -5 no segundo
    db.add_all(
        [
            MetricaTalhao(talhao_id=objs[0].id, data=date(2024, 1, 1), ndvi_medio=0.7, balanco_hidrico_mm=10),
            MetricaTalhao(
                talhao_id=objs[0].id, data=date(2024, 1, 5), ndvi_medio=0.6, balanco_hidrico_mm=-30
            ),
            MetricaTalhao(talhao_id=objs[1].id, data=date(2024, 1, 5), ndvi_medio=0.5, balanco_hidrico_mm=-5),
        ]
    )
    db.commit()
    return objs


def test_lista_paginada(client, agronomo_token, talhoes):
    h = auth(agronomo_token)
    r = client.get("/api/talhoes?page=1&size=2", headers=h)
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["total"] == 4 and corpo["page"] == 1 and corpo["size"] == 2
    assert len(corpo["items"]) == 2
    r2 = client.get("/api/talhoes?page=2&size=2", headers=h).json()
    assert len(r2["items"]) == 2
    ids = {i["id"] for i in corpo["items"]} | {i["id"] for i in r2["items"]}
    assert len(ids) == 4
    assert client.get("/api/talhoes?page=3&size=2", headers=h).json()["items"] == []


def test_lista_exige_login(client, talhoes):
    assert client.get("/api/talhoes").status_code == 401


def test_busca_e_filtro_sistema(client, agronomo_token, talhoes):
    h = auth(agronomo_token)
    r = client.get("/api/talhoes?busca=silagem", headers=h).json()
    assert r["total"] == 2
    r = client.get("/api/talhoes?sistema=AGRO_4_0", headers=h).json()
    assert {i["nome"] for i in r["items"]} == {"Grão 4.0", "Silagem 4.0"}


def test_filtro_deficit_min(client, agronomo_token, talhoes):
    # deficit_min=20 → talhões cujo último balanço é <= -20 mm
    r = client.get("/api/talhoes?deficit_min=20", headers=auth(agronomo_token)).json()
    assert [i["nome"] for i in r["items"]] == ["Grão 4.0"]


def test_ordenacao(client, agronomo_token, talhoes):
    r = client.get("/api/talhoes?sort=-area_ha", headers=auth(agronomo_token)).json()
    assert [i["nome"] for i in r["items"]][0] == "Grão 4.0"
    r = client.get("/api/talhoes?sort=nome", headers=auth(agronomo_token)).json()
    assert r["items"][0]["nome"] == "Grão 4.0"


def test_sort_invalido_400(client, agronomo_token, talhoes):
    assert client.get("/api/talhoes?sort=senha", headers=auth(agronomo_token)).status_code == 400


def test_detalhe_com_ultima_metrica(client, agronomo_token, talhoes):
    r = client.get(f"/api/talhoes/{talhoes[0].id}", headers=auth(agronomo_token))
    assert r.status_code == 200
    assert r.json()["ultima_metrica"]["data"] == "2024-01-05"
    assert r.json()["ultima_metrica"]["ndvi_medio"] == 0.6


def test_detalhe_404(client, agronomo_token):
    r = client.get("/api/talhoes/999", headers=auth(agronomo_token))
    assert r.status_code == 404
    assert r.json() == {"detail": "Talhão não encontrado"}


def test_metricas_intervalo(client, agronomo_token, talhoes):
    url = f"/api/talhoes/{talhoes[0].id}/metricas?de=2024-01-02&ate=2024-01-31"
    r = client.get(url, headers=auth(agronomo_token)).json()
    assert [m["data"] for m in r] == ["2024-01-05"]


def test_solo_com_classificacao(client, agronomo_token, talhoes, db):
    db.add(
        LeituraSolo(
            talhao_id=talhoes[0].id, ponto="P1", data_coleta=date(2024, 1, 1), ph=4.8, v_pct=45, p=20, k=0.3
        )
    )
    db.commit()
    r = client.get(f"/api/talhoes/{talhoes[0].id}/solo", headers=auth(agronomo_token)).json()
    assert r[0]["ponto"] == "P1"
    assert r[0]["classificacao"]["ph"] == "BAIXO"
    assert r[0]["classificacao"]["v_pct"] == "BAIXO"
    assert r[0]["classificacao"]["p"] == "ADEQUADO"


def test_clima_agregado_por_dia(client, agronomo_token, db):
    db.add_all(
        [
            LeituraClima(
                data_hora=datetime(2024, 1, 1, 10), temp_med=20, temp_min=18, temp_max=22, chuva_mm=1
            ),
            LeituraClima(
                data_hora=datetime(2024, 1, 1, 14), temp_med=30, temp_min=25, temp_max=33, chuva_mm=2
            ),
            LeituraClima(
                data_hora=datetime(2024, 1, 2, 10), temp_med=22, temp_min=20, temp_max=24, chuva_mm=0
            ),
        ]
    )
    db.commit()
    r = client.get("/api/clima?de=2024-01-01&ate=2024-01-02&agregacao=dia", headers=auth(agronomo_token))
    assert r.status_code == 200
    dias = r.json()
    assert len(dias) == 2
    assert dias[0]["data"] == "2024-01-01"
    assert dias[0]["temp_med"] == 25
    assert dias[0]["temp_min"] == 18 and dias[0]["temp_max"] == 33
    assert dias[0]["chuva_mm"] == 3
