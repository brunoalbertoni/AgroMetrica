from datetime import date

import pytest
from sqlalchemy import func, select

from app.models import LeituraClima, LeituraSolo, MetricaTalhao, Talhao, Upload
from tests.conftest import auth

METOS_OK = (
    "Data;HC Air temperature [°C] avg;HC Air temperature [°C] min;HC Air temperature [°C] max;"
    "Precipitation [mm] sum;HC Relative humidity [%] avg;Wind speed [m/s] avg;ETo [mm]\n"
    "01/02/2024 10:00;25,4;22,1;28,0;0,0;60,5;2,0;0,3\n"
    "01/02/2024 11:00;27,0;24,0;29,5;1,2;58,0;2,5;0,4\n"
    "02/02/2024 10:00;24,0;21,0;26,0;0,0;70,0;1,0;0,2\n"
)

METOS_UMA_RUIM = (
    "Data;HC Air temperature [°C] avg;Precipitation [mm] sum\n"
    "01/02/2024 10:00;25,4;0,0\n"
    "data-invalida;26,0;0,0\n"
    "01/02/2024 12:00;abc;0,0\n"
    "01/02/2024 13:00;27,0;0,5\n"
)


def _enviar(client, token, tipo, conteudo, nome="arquivo.csv"):
    return client.post(
        f"/api/uploads/{tipo}",
        files={"arquivo": (nome, conteudo.encode("utf-8"), "text/csv")},
        headers=auth(token),
    )


def test_upload_clima_metos_valido(client, agronomo_token, db):
    r = _enviar(client, agronomo_token, "clima", METOS_OK)
    assert r.status_code == 200, r.text
    assert r.json() == {"linhas_ok": 3, "linhas_erro": 0, "erros": []}
    leitura = db.scalar(select(LeituraClima).order_by(LeituraClima.data_hora))
    assert leitura.data_hora.day == 1 and leitura.data_hora.month == 2  # dayfirst
    assert leitura.temp_med == pytest.approx(25.4)
    assert leitura.vento_kmh == pytest.approx(7.2)  # m/s → km/h
    assert db.scalar(select(func.count()).select_from(Upload)) == 1


def test_upload_linhas_invalidas_nao_derrubam_lote(client, agronomo_token, db):
    r = _enviar(client, agronomo_token, "clima", METOS_UMA_RUIM)
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["linhas_ok"] == 2 and corpo["linhas_erro"] == 2
    assert [e["linha"] for e in corpo["erros"]] == [3, 4]
    assert db.scalar(select(func.count()).select_from(LeituraClima)) == 2


def test_upload_sem_coluna_obrigatoria_400(client, agronomo_token):
    r = _enviar(client, agronomo_token, "clima", "Data;Umidade\n01/02/2024 10:00;60\n")
    assert r.status_code == 400
    assert "temp_med" in r.json()["detail"]


def test_upload_repetido_nao_duplica(client, agronomo_token, db):
    _enviar(client, agronomo_token, "clima", METOS_OK)
    r = _enviar(client, agronomo_token, "clima", METOS_OK)
    assert r.json()["linhas_ok"] == 3
    assert db.scalar(select(func.count()).select_from(LeituraClima)) == 3


def test_upload_tipo_invalido_400(client, agronomo_token):
    assert _enviar(client, agronomo_token, "foo", METOS_OK).status_code == 400


def test_upload_exige_login(client):
    r = client.post("/api/uploads/clima", files={"arquivo": ("a.csv", b"x", "text/csv")})
    assert r.status_code == 401


@pytest.fixture
def talhao(db):
    t = Talhao(nome="Grão 4.0", area_ha=10, cultura="Milho", sistema="AGRO_4_0", finalidade="GRAO")
    db.add(t)
    db.commit()
    return t


def test_upload_ndvi_por_nome_do_talhao(client, agronomo_token, db, talhao):
    csv = (
        "field,date,ndvi_mean,ndvi_min,ndvi_max\n"
        "Grão 4.0,2024-01-05,0.71,0.5,0.85\n"
        "Inexistente,2024-01-05,0.5,0.4,0.6\n"
    )
    r = _enviar(client, agronomo_token, "ndvi", csv)
    assert r.json()["linhas_ok"] == 1 and r.json()["linhas_erro"] == 1
    assert "Inexistente" in r.json()["erros"][0]["erro"]
    m = db.scalar(select(MetricaTalhao))
    assert m.data == date(2024, 1, 5) and m.ndvi_medio == pytest.approx(0.71)


def test_upload_solo(client, agronomo_token, db, talhao):
    csv = f"talhao_id;ponto;zona;data_coleta;pH;MO;P;K;V%\n{talhao.id};P1;1;10/01/2024;5,2;30;12,5;0,2;55\n"
    r = _enviar(client, agronomo_token, "solo", csv)
    assert r.json() == {"linhas_ok": 1, "linhas_erro": 0, "erros": []}
    s = db.scalar(select(LeituraSolo))
    assert s.ph == pytest.approx(5.2) and s.v_pct == pytest.approx(55) and s.data_coleta == date(2024, 1, 10)


def test_upload_colheita_agrega_por_talhao(client, agronomo_token, db, talhao):
    csv = "talhao;data;produtividade_kg_ha\nGrão 4.0;20/03/2024;9000\nGrão 4.0;20/03/2024;11000\n"
    r = _enviar(client, agronomo_token, "colheita", csv)
    assert r.json()["linhas_ok"] == 2
    m = db.scalar(select(MetricaTalhao))
    assert m.produtividade_kg_ha == pytest.approx(10000)
