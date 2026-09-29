from datetime import date
from pathlib import Path

import cv2
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from sqlalchemy import select

from app.core.config import settings
from app.models import Imagem, MetricaTalhao, Talhao
from app.services import imagem as svc
from tests.conftest import auth


@pytest.fixture
def talhao(db):
    t = Talhao(nome="T1", area_ha=10, cultura="Milho", sistema="AGRO_4_0", finalidade="GRAO")
    db.add(t)
    db.commit()
    return t


def _foto_rgb(caminho: Path, verde=True):
    img = np.zeros((40, 60, 3), dtype=np.uint8)  # BGR
    if verde:
        img[:, :] = (40, 180, 60)  # B, G, R → vegetação
    else:
        img[:, :] = (60, 90, 150)  # solo exposto
    cv2.imwrite(str(caminho), img)


def test_vari_vegetacao_positivo_solo_negativo():
    verde = np.full((4, 4, 3), (40, 180, 60), dtype=np.uint8)
    solo = np.full((4, 4, 3), (60, 90, 150), dtype=np.uint8)
    assert svc.calcular_vari(verde).mean() > 0.3
    assert svc.calcular_vari(solo).mean() < 0


def test_vari_nao_divide_por_zero():
    preto = np.zeros((3, 3, 3), dtype=np.uint8)
    v = svc.calcular_vari(preto)
    assert np.isfinite(v).all()


def test_mapa_vari_gera_arquivo_colorido(tmp_path):
    origem = tmp_path / "folha.png"
    _foto_rgb(origem)
    destino = tmp_path / "vari.png"
    estat = svc.gerar_mapa_vari(origem, destino)
    assert destino.exists()
    saida = cv2.imread(str(destino))
    assert saida.shape == (40, 60, 3)
    assert estat["indice"] == "VARI" and estat["media"] > 0.3


def test_estatisticas_geotiff_usa_mascara_da_banda_3(tmp_path):
    caminho = tmp_path / "ndvi.tif"
    ndvi = np.array([[0.2, 0.4], [0.6, 0.9]], dtype="float32")
    mascara = np.array([[0, 1], [1, 1]], dtype="float32")  # pixel 0.2 fora do talhão
    with rasterio.open(
        caminho,
        "w",
        driver="GTiff",
        width=2,
        height=2,
        count=3,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(0, 2, 1, 1),
    ) as dst:
        dst.write(ndvi, 1)
        dst.write(np.zeros_like(ndvi), 2)
        dst.write(mascara, 3)
    e = svc.estatisticas_ndvi_geotiff(caminho)
    assert e["ndvi_min"] == pytest.approx(0.4)
    assert e["ndvi_max"] == pytest.approx(0.9)
    assert e["ndvi_medio"] == pytest.approx((0.4 + 0.6 + 0.9) / 3, abs=1e-4)


def test_processar_geotiff_grava_metrica(db, talhao, tmp_path):
    caminho = tmp_path / "n.tif"
    with rasterio.open(caminho, "w", driver="GTiff", width=1, height=1, count=3, dtype="float32") as dst:
        dst.write(np.array([[0.5]], dtype="float32"), 1)
        dst.write(np.array([[0]], dtype="float32"), 2)
        dst.write(np.array([[1]], dtype="float32"), 3)
    img = Imagem(
        talhao_id=talhao.id, tipo="NDVI_GEOTIFF", caminho=str(caminho), data_captura=date(2024, 3, 1)
    )
    db.add(img)
    db.commit()
    svc.processar_imagem(img.id)
    db.expire_all()
    assert db.get(Imagem, img.id).status == "PROCESSADO"
    m = db.scalar(select(MetricaTalhao))
    assert m.data == date(2024, 3, 1) and m.ndvi_medio == pytest.approx(0.5)


def test_processar_arquivo_invalido_marca_erro(db, talhao, tmp_path):
    ruim = tmp_path / "x.png"
    ruim.write_bytes(b"nao e imagem")
    img = Imagem(talhao_id=talhao.id, tipo="FOLHA", caminho=str(ruim))
    db.add(img)
    db.commit()
    svc.processar_imagem(img.id)
    db.expire_all()
    assert db.get(Imagem, img.id).status == "ERRO"


def test_post_imagem_rgb_202_e_processa(client, agronomo_token, talhao, tmp_path):
    foto = tmp_path / "folha.jpg"
    _foto_rgb(foto)
    r = client.post(
        "/api/imagens",
        data={"talhao_id": str(talhao.id), "tipo": "FOLHA"},
        files={"arquivo": ("folha.jpg", foto.read_bytes(), "image/jpeg")},
        headers=auth(agronomo_token),
    )
    assert r.status_code == 202, r.text
    iid = r.json()["id"]
    # TestClient executa as BackgroundTasks antes de devolver a resposta
    info = client.get(f"/api/imagens/{iid}", headers=auth(agronomo_token)).json()
    assert info["status"] == "PROCESSADO"
    assert info["indice"] == "VARI"
    assert info["url"].startswith("/api/arquivos/")
    assert info["url_processada"].startswith("/api/arquivos/")
    assert (settings.storage_path / info["caminho_processado"]).exists()
    assert client.get(info["url_processada"], headers=auth(agronomo_token)).status_code == 200


def test_post_imagem_talhao_inexistente_404(client, agronomo_token, tmp_path):
    r = client.post(
        "/api/imagens",
        data={"talhao_id": "999", "tipo": "FOLHA"},
        files={"arquivo": ("f.jpg", b"123", "image/jpeg")},
        headers=auth(agronomo_token),
    )
    assert r.status_code == 404


def test_arquivos_bloqueia_path_traversal(client, agronomo_token):
    r = client.get("/api/arquivos/..%2F..%2Fsegredo.txt", headers=auth(agronomo_token))
    assert r.status_code == 404
