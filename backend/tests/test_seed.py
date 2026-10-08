import json
from datetime import date, datetime

import pytest
from sqlalchemy import func, select

from app.models import (
    Alerta,
    Diagnostico,
    Imagem,
    LeituraClima,
    LeituraSolo,
    MetricaTalhao,
    OperacaoTalhao,
    Praga,
    Produto,
    Talhao,
    Usuario,
)
from app.services import diagnostico as diag_svc
from app.services import geo, storage
from scripts import seed_farmlab

# dois talhões quadrados lado a lado (lon, lat), no formato MULTIPOLYGON do EKOS
_A = [(-49.980, -22.250), (-49.970, -22.250), (-49.970, -22.240), (-49.980, -22.240), (-49.980, -22.250)]
_B = [(x - 0.02, y) for x, y in _A]


def _multi(anel):
    return "MULTIPOLYGON (((" + ", ".join(f"{x} {y}" for x, y in anel) + ")))"


def _trecho(lon, lat, d=0.0001):
    return f"POLYGON (({lon} {lat}, {lon + d} {lat}, {lon + d} {lat + d}, {lon} {lat + d}, {lon} {lat}))"


def _mercator(lon, lat):
    import math

    x = math.radians(lon) * 6378137
    y = math.log(math.tan(math.pi / 4 + math.radians(lat) / 2)) * 6378137
    return x, y


def _escrever(pasta, nome, texto):
    pasta.mkdir(parents=True, exist_ok=True)
    (pasta / nome).write_text(texto, encoding="utf-8")


@pytest.fixture
def farmlab(tmp_path):
    raiz = tmp_path / "farmlab"
    ekos = raiz / "EKOS - Telemetria" / "CSV"
    _escrever(
        ekos / "Fields",
        "fields.csv",
        "idField;idFarm;fieldName;fieldGeom\n"
        f"101;1;Grão 4.0 - 19,3 ha;{_multi(_A)}\n"
        f"102;1;Grão Convencional - 16,6 ha;{_multi(_B)}\n",
    )
    _escrever(
        ekos / "Pest",
        "pest_details.csv",
        "alert;control;culture;damage;detectionName;namePopular;nameScientific\n"
        "2;4;Milho;5;Spodoptera spp.;Lagarta Spodoptera;Spodoptera spp.\n"
        "15;20;Milho;30;Cigarrinha;Cigarrinha;Dalbulus maidis\n"
        "15;20;Milho;30;Cigarrinha;Cigarrinha;Dalbulus maidis\n"
        "1;2;Soja;3;sa;Percevejo Soja;X\n",
    )
    _escrever(
        ekos / "Pest",
        "traps_list.csv",
        "code;id;latitude;longitude\nARM1;9001;-22.245;-49.975\nARM2;9002;-22.245;-49.995\n",
    )
    _escrever(ekos / "Pest", "traps_data.csv", "trapCode;trapId;primaryPest\nARM2;9002;Cigarrinha\n")
    caixas = [
        {"xmin": 20, "ymin": 10, "xmax": 60, "ymax": 30, "confidence": 0.9, "name": "Spodoptera spp."}
        for _ in range(3)
    ] + [{"xmin": 100, "ymin": 50, "xmax": 140, "ymax": 90, "confidence": 0.8, "name": "Cigarrinha"}]
    deteccao = json.dumps(["3 Spodoptera spp., 1 Cigarrinha, ", json.dumps(caixas)]).replace('"', '""')
    _escrever(
        ekos / "Pest",
        "traps_events.csv",
        "code;createdAt;data;detection;pestCount;type;trapId\n"
        f'ARM1;2026-02-06T12:00:00.000Z;https://fotos.exemplo/a1.jpg;"{deteccao}";4;IMAGE;9001\n'
        "ARM2;2026-02-07T12:00:00.000Z;https://fotos.exemplo/a2.jpg;;40;IMAGE;9002\n"
        "ARM1;2026-02-07T13:00:00.000Z;;;0;PING;9001\n",
    )
    cab = "geometry;Timestamp;Date Time;Machine Name;Service Order;Operator Number;Operator Name;Operation;Team"
    _escrever(
        ekos / "Layers",
        "LAYER_MAP_FERTILIZATION.csv",
        f"{cab};Area - ha;AppliedDos - kg/ha;Configured - kg/ha;Weight - kg\n"
        f"{_trecho(-49.975, -22.245)};1;01/09/2025 10:00:00;M;1;1;;CALAGEM;T;10;1500;1600;1\n"
        f"{_trecho(-49.974, -22.245)};1;02/09/2025 10:00:00;M;1;1;;CALAGEM;T;10;1700;1600;1\n"
        f"{_trecho(-49.975, -22.245)};1;20/09/2025 10:00:00;M;1;1;;CALAGEM;T;0.1;900;1600;1\n"
        f"{_trecho(-49.995, -22.245)};1;11/11/2025 10:00:00;M;1;1;;PLANTIO MILHO GRÃO;T;5;290;300;1\n"
        f"{_trecho(-50.100, -22.245)};1;11/11/2025 10:00:00;M;1;1;;CALAGEM;T;5;1000;1000;1\n",
    )
    _escrever(
        ekos / "Layers",
        "LAYER_MAP_PLANTING.csv",
        f"{cab};Area - ha;Population - ha\n"
        f"{_trecho(-49.995, -22.245)};1;11/11/2025 17:03:37;M;1;1;;PLANTIO MILHO GRÃO;T;5;62000\n"
        f"{_trecho(-49.975, -22.245)};1;13/11/2025 17:03:37;M;1;1;;PLANTIO MILHO GRÃO;T;5;60000\n",
    )
    _escrever(
        ekos / "Layers",
        "LAYER_MAP_GRAIN_HARVESTING.csv",
        f"{cab};Area - ha;Yield - kg/ha;Weight - kg;Humidity - %\n"
        f"{_trecho(-49.975, -22.245)};1;20/02/2026 10:00:00;C;1;1;;COLHEITA GRÃO;T;1;9000;1;1\n"
        f"{_trecho(-49.975, -22.245)};1;21/02/2026 10:00:00;C;1;1;;COLHEITA GRÃO;T;3;11000;1;1\n"
        f"{_trecho(-49.995, -22.245)};1;21/02/2026 10:00:00;C;1;1;;CALAGEM;T;3;99999;1;1\n"
        f"{_trecho(-50.100, -22.245)};1;21/02/2026 10:00:00;C;1;1;;COLHEITA GRÃO;T;3;99999;1;1\n",
    )
    _escrever(
        ekos / "Inputs",
        "agricultural_inputs.csv",
        "agricultural_input_name;agricultural_input_brand;agricultural_input_class\n"
        "CALCÁRIO;GUAPIARA;DOLOMITICO\nNK501VIP3;;Sementes\nFOLIAR X;;Foliar\n",
    )
    _escrever(
        raiz / "Metos - Estação" / "CSV",
        "Relatório Horário.csv",
        "﻿Data;Estação;Radiação Solar (W/m2);Precipitação (mm);Vel do Vento Média (km/h);"
        "Temp. Mínima (°C);Temp. Média (°C);Temp. Máxima (°C);Umidade Rel. Média (%);Evapotranspiração (mm)\n"
        '"13/11/2025 - 00:00 / GMT - 03:00";"E";0;0;8,7;19,86;19,97;20,12;94,47;4,6\n'
        '"13/11/2025 - 01:00 / GMT - 03:00";"E";0;1,2;8,9;19,45;19,58;19,84;95,19;\n',
    )
    xa, ya = _mercator(-49.975, -22.245)
    _escrever(
        raiz / "OneSoil" / "CSV",
        "ndvi_metadata.csv",
        "filename,season_id,crs,bounds_left,bounds_bottom,bounds_right,bounds_top,b1_min,b1_max,b1_mean\n"
        f"ndvi_raw_s1_2025-11-10.tiff,s1,EPSG:3857,{xa - 50},{ya - 50},{xa + 50},{ya + 50},0.1,0.8,0.55\n"
        f"ndvi_raw_s1_2025-11-13.tiff,s1,EPSG:3857,{xa - 50},{ya - 50},{xa + 50},{ya + 50},,,\n",
    )
    (raiz / "OneSoil" / "JPG").mkdir(parents=True)
    (raiz / "OneSoil" / "JPG" / "ndvi_raw_s1_2025-11-10.jpg").write_bytes(b"jpg")
    _escrever(
        raiz / "Cropman" / "CSV",
        "soil_analysis.csv",
        "﻿AMOSTRA;PHCACL2;K;P;SATB;CA;PHCACL2_2;K_2\n1;5,23;3,75;19,8;66,78;18,39;4,5;1,2\n2;6;1;1;1;1;;\n",
    )
    return raiz


@pytest.fixture
def sem_download(monkeypatch):
    """Simula o S3: toda foto tem 200×100 px e é gravada no storage."""

    def falso(urls):
        saida = {}
        for url in urls:
            caminho = f"{seed_farmlab.PASTA_FOTOS}/{url.rsplit('/', 1)[-1]}"
            destino = storage.caminho_absoluto(caminho)
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(b"jpg")
            saida[url] = (caminho, 200, 100)
        return saida

    monkeypatch.setattr(seed_farmlab, "baixar_fotos", falso)


def _contar(db, modelo):
    return db.scalar(select(func.count()).select_from(modelo))


def _talhoes(db):
    return {t.nome: t for t in db.scalars(select(Talhao))}


def test_importa_talhoes_do_ekos(db, farmlab, sem_download):
    seed_farmlab.executar(db, farmlab)
    t = _talhoes(db)
    assert set(t) == {"Grão 4.0", "Grão Convencional"}
    assert t["Grão 4.0"].sistema == "AGRO_4_0" and t["Grão 4.0"].finalidade == "GRAO"
    assert t["Grão Convencional"].sistema == "CONVENCIONAL"
    assert float(t["Grão 4.0"].area_ha) == 19.3
    assert t["Grão 4.0"].codigo_externo == "101"
    assert t["Grão 4.0"].geometria.startswith("POLYGON((")
    assert t["Grão 4.0"].data_plantio == date(2025, 11, 13)
    assert t["Grão Convencional"].data_plantio == date(2025, 11, 11)
    assert db.scalar(select(Usuario).where(Usuario.perfil == "ADMIN")) is not None


def test_importa_pragas_so_da_cultura_sem_repetir(db, farmlab, sem_download):
    seed_farmlab.executar(db, farmlab)
    pragas = {p.nome: p for p in db.scalars(select(Praga))}
    assert set(pragas) == {"Lagarta Spodoptera", "Cigarrinha"}
    assert (pragas["Cigarrinha"].limiar_alerta, pragas["Cigarrinha"].limiar_dano) == (15, 30)


def test_importa_clima_do_metos(db, farmlab, sem_download):
    seed_farmlab.executar(db, farmlab)
    leituras = db.scalars(select(LeituraClima).order_by(LeituraClima.data_hora)).all()
    assert [x.data_hora for x in leituras] == [datetime(2025, 11, 13, 0), datetime(2025, 11, 13, 1)]
    assert leituras[0].temp_med == pytest.approx(19.97)
    assert leituras[0].etp_mm == pytest.approx(4.6) and leituras[1].etp_mm is None
    assert leituras[1].chuva_mm == pytest.approx(1.2)
    assert leituras[0].vento_kmh == pytest.approx(8.7) and leituras[0].umidade_med == pytest.approx(94.47)


def test_ndvi_vai_para_o_talhao_da_imagem(db, farmlab, sem_download):
    seed_farmlab.executar(db, farmlab)
    t = _talhoes(db)["Grão 4.0"]
    metricas = db.scalars(select(MetricaTalhao).where(MetricaTalhao.ndvi_medio.is_not(None))).all()
    assert [(m.talhao_id, m.data, m.ndvi_medio) for m in metricas] == [(t.id, date(2025, 11, 10), 0.55)]
    img = db.scalar(select(Imagem).where(Imagem.tipo == "NDVI_GEOTIFF"))
    assert img.talhao_id == t.id and storage.caminho_absoluto(img.caminho).exists()


def test_operacoes_agregadas_por_talhao(db, farmlab, sem_download):
    seed_farmlab.executar(db, farmlab)
    t = _talhoes(db)
    ops = {(o.talhao_id, o.operacao): o for o in db.scalars(select(OperacaoTalhao))}
    calagem = ops[(t["Grão 4.0"].id, "Calagem")]
    assert calagem.area_ha == pytest.approx(20.1)
    assert calagem.dose_aplicada == pytest.approx((1500 * 10 + 1700 * 10 + 900 * 0.1) / 20.1, abs=0.1)
    # o trecho de 0,1 ha em 20/09 é sobra: não estica o período da operação
    assert (calagem.data_inicio, calagem.data_fim) == (date(2025, 9, 1), date(2025, 9, 2))
    adubacao = ops[(t["Grão Convencional"].id, "Adubação de plantio")]
    assert (adubacao.dose_aplicada, adubacao.dose_configurada, adubacao.unidade) == (290, 300, "kg/ha")
    plantio = ops[(t["Grão Convencional"].id, "Plantio")]
    assert (plantio.dose_aplicada, plantio.unidade) == (62000, "plantas/ha")
    assert len(ops) == 4  # o trecho fora dos talhões não entra


def test_colheita_so_de_trechos_de_colheita_dentro_do_talhao(db, farmlab, sem_download):
    seed_farmlab.executar(db, farmlab)
    t = _talhoes(db)
    prod = db.scalars(select(MetricaTalhao).where(MetricaTalhao.produtividade_kg_ha.is_not(None))).all()
    assert [(m.talhao_id, m.data, m.produtividade_kg_ha) for m in prod] == [
        (t["Grão 4.0"].id, date(2026, 2, 21), 10500.0)
    ]


def test_insumos_com_dose_das_operacoes(db, farmlab, sem_download):
    seed_farmlab.executar(db, farmlab)
    produtos = {p.nome_comercial: p for p in db.scalars(select(Produto))}
    assert set(produtos) == {"CALCÁRIO GUAPIARA", "NK501VIP3"}  # foliar sem aplicação registrada fica de fora
    assert produtos["CALCÁRIO GUAPIARA"].classe == "CORRETIVO"
    assert (produtos["CALCÁRIO GUAPIARA"].dose_min, produtos["CALCÁRIO GUAPIARA"].dose_max) == (1600, 1600)
    assert produtos["NK501VIP3"].classe == "SEMENTE"
    assert (produtos["NK501VIP3"].dose_min, produtos["NK501VIP3"].dose_max) == (60000, 62000)


def test_armadilhas_viram_diagnosticos_com_caixas(db, farmlab, sem_download):
    seed_farmlab.executar(db, farmlab)
    t = _talhoes(db)
    diags = {d.praga.nome + "@" + d.talhao.nome: d for d in db.scalars(select(Diagnostico))}
    lagarta = diags["Lagarta Spodoptera@Grão 4.0"]
    assert lagarta.detalhes["contagem"] == 3 and lagarta.severidade == "MEDIA"  # 3 ≥ controle... não: alerta 2
    assert lagarta.detalhes["data"] == "2026-02-06T09:00:00"  # UTC → horário local
    assert lagarta.detalhes["bboxes"][0] == {
        "x": 0.1,
        "y": 0.1,
        "w": 0.2,
        "h": 0.2,
        "rotulo": "Lagarta Spodoptera",
        "confianca": 0.9,
    }
    assert lagarta.confianca == 0.9
    img = db.get(Imagem, lagarta.imagem_id)
    assert img.tipo == "ARMADILHA" and img.talhao_id == t["Grão 4.0"].id
    # 1 cigarrinha fica abaixo do limiar de alerta (15): sem diagnóstico
    assert "Cigarrinha@Grão 4.0" not in diags
    # foto sem detecção: toda a contagem vai para a praga-alvo da armadilha
    cigarrinha = diags["Cigarrinha@Grão Convencional"]
    assert cigarrinha.detalhes["contagem"] == 40 and cigarrinha.severidade == "ALTA"
    assert cigarrinha.detalhes["bboxes"] == []
    assert _contar(db, Alerta) == 2


def test_solo_precisa_do_vinculo_de_amostras(db, farmlab, sem_download):
    seed_farmlab.executar(db, farmlab)
    assert _contar(db, LeituraSolo) == 0

    (farmlab / "amostras_solo.csv").write_text(
        "amostra;talhao;data_coleta\n1;Grão 4.0;15/08/2025\n2;102;15/08/2025\n", encoding="utf-8"
    )
    seed_farmlab.executar(db, farmlab)
    t = _talhoes(db)
    leituras = {x.ponto: x for x in db.scalars(select(LeituraSolo))}
    assert set(leituras) == {"1 (0–20 cm)", "1 (20–40 cm)", "2 (0–20 cm)"}
    superficie = leituras["1 (0–20 cm)"]
    assert superficie.talhao_id == t["Grão 4.0"].id and superficie.data_coleta == date(2025, 8, 15)
    assert superficie.ph == pytest.approx(5.23) and superficie.v_pct == pytest.approx(66.78)
    assert superficie.k == pytest.approx(0.375) and superficie.ca == pytest.approx(1.839)  # mmolc → cmolc
    assert leituras["1 (20–40 cm)"].k == pytest.approx(0.12)
    assert leituras["2 (0–20 cm)"].talhao_id == t["Grão Convencional"].id


def test_seed_e_idempotente(db, farmlab, sem_download):
    seed_farmlab.executar(db, farmlab)
    modelos = (Talhao, Diagnostico, Alerta, Produto, Praga, Usuario, OperacaoTalhao, MetricaTalhao, Imagem)
    antes = {m: _contar(db, m) for m in modelos}
    seed_farmlab.executar(db, farmlab)
    assert {m: _contar(db, m) for m in modelos} == antes


def test_limpar_apaga_dados_mas_mantem_usuarios(db, farmlab, sem_download):
    seed_farmlab.executar(db, farmlab)
    velho = Talhao(nome="Inventado", area_ha=1, cultura="Milho", sistema="AGRO_4_0", finalidade="GRAO")
    db.add(velho)
    db.commit()
    seed_farmlab.executar(db, farmlab, limpar=True)
    assert "Inventado" not in _talhoes(db)
    assert _contar(db, Usuario) == 2


def test_armadilha_repetida_nao_duplica(db):
    t = Talhao(nome="T", area_ha=1, cultura="Milho", sistema="AGRO_4_0", finalidade="GRAO")
    p = Praga(nome="Lagarta", limiar_alerta=1, limiar_controle=2, limiar_dano=3)
    db.add_all([t, p])
    db.commit()
    primeiro = diag_svc.registrar_armadilha(db, t.id, p.id, contagem=5, data=datetime(2024, 1, 1))
    segundo = diag_svc.registrar_armadilha(db, t.id, p.id, contagem=5, data=datetime(2024, 1, 1))
    assert segundo.id == primeiro.id
    assert _contar(db, Diagnostico) == 1 and _contar(db, Alerta) == 1


def test_geo_localiza_ponto_e_converte_multipolygon():
    wkt = _multi(_A)
    assert geo.para_polygon(wkt).startswith("POLYGON((-49.98 -22.25")
    loc = geo.Localizador({1: wkt, 2: _multi(_B)})
    assert loc.talhao(-49.975, -22.245) == 1
    assert loc.talhao(-49.995, -22.245) == 2
    assert loc.talhao(-50.1, -22.245) is None
    lon, lat = geo.mercator_para_lonlat(*_mercator(-49.975, -22.245))
    assert (round(lon, 6), round(lat, 6)) == (-49.975, -22.245)
    assert geo.area_ha(wkt) == pytest.approx(1.03 * 1.11 * 100 * 0.925, rel=0.05)
