"""Processamento de imagens: índice RGB (VARI) em fotos e estatísticas de NDVI em GeoTIFF."""

import logging
from datetime import date, datetime
from pathlib import Path

import cv2
import numpy as np
import rasterio
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models import Imagem, MetricaTalhao, Talhao
from app.models.enums import StatusImagem, TipoImagem
from app.services import storage
from app.services.upsert import upsert

log = logging.getLogger(__name__)

TIPOS_RGB = {TipoImagem.FOLHA, TipoImagem.ORTOMOSAICO}


def _lut_vermelho_amarelo_verde() -> np.ndarray:
    """Tabela 256×1×3 (BGR) vermelho → amarelo → verde para cv2.applyColorMap."""
    lut = np.zeros((256, 1, 3), dtype=np.uint8)
    for i in range(256):
        t = i / 255
        if t < 0.5:
            r, g = 215, int(48 + (255 - 48) * (t / 0.5))
        else:
            r, g = int(255 - (255 - 26) * ((t - 0.5) / 0.5)), int(255 - (255 - 150) * ((t - 0.5) / 0.5))
        lut[i, 0] = (40, g, r)
    return lut


_LUT = _lut_vermelho_amarelo_verde()


def indice_nome(tipo: TipoImagem) -> str | None:
    """Rótulo exibido na interface. Foto RGB nunca é chamada de NDVI."""
    if tipo in TIPOS_RGB:
        return "VARI"
    if tipo == TipoImagem.NDVI_GEOTIFF:
        return "NDVI"
    return None


EXTENSOES = {
    TipoImagem.FOLHA: {".jpg", ".jpeg", ".png"},
    TipoImagem.ORTOMOSAICO: {".jpg", ".jpeg", ".png", ".tif", ".tiff"},
    TipoImagem.ARMADILHA: {".jpg", ".jpeg", ".png"},
    TipoImagem.NDVI_GEOTIFF: {".tif", ".tiff"},
}


def sem_fuso(momento: datetime | None) -> datetime | None:
    """Converte datas com fuso para o horário local sem fuso (o banco guarda datas ingênuas)."""
    if momento is None or momento.tzinfo is None:
        return momento
    return momento.astimezone().replace(tzinfo=None)


def receber(
    db: Session,
    conteudo: bytes,
    nome_arquivo: str,
    talhao_id: int,
    tipo: TipoImagem,
    data_captura: datetime | None,
    usuario_id: int,
) -> Imagem:
    """Valida e grava a imagem enviada; o processamento roda depois, em segundo plano."""
    if db.get(Talhao, talhao_id) is None:
        raise HTTPException(404, "Talhão não encontrado")
    extensao = Path(nome_arquivo).suffix.lower()
    if extensao not in EXTENSOES[tipo]:
        aceitas = ", ".join(sorted(EXTENSOES[tipo]))
        raise HTTPException(
            400, f"Formato {extensao or 'sem extensão'} não aceito para {tipo.value}. Use {aceitas}."
        )
    img = Imagem(
        talhao_id=talhao_id,
        tipo=tipo,
        caminho=storage.salvar(conteudo, "originais", nome_arquivo),
        data_captura=sem_fuso(data_captura) or datetime.now(),
        status=StatusImagem.PENDENTE,
        enviado_por=usuario_id,
    )
    db.add(img)
    db.commit()
    db.refresh(img)
    return img


def representar(img: Imagem) -> dict:
    return {
        "id": img.id,
        "talhao_id": img.talhao_id,
        "tipo": img.tipo,
        "status": img.status,
        "caminho": img.caminho,
        "caminho_processado": img.caminho_processado,
        "url": storage.url(img.caminho),
        "url_processada": storage.url(img.caminho_processado),
        "indice": indice_nome(img.tipo),
        "data_captura": img.data_captura,
    }


def calcular_vari(bgr: np.ndarray) -> np.ndarray:
    """VARI = (G − R) / (G + R − B), recortado em [−1, 1]; denominador zero vira 0."""
    b, g, r = (bgr[..., i].astype(np.float32) for i in range(3))
    denominador = g + r - b
    with np.errstate(divide="ignore", invalid="ignore"):
        vari = np.where(np.abs(denominador) < 1e-6, 0.0, (g - r) / denominador)
    return np.clip(vari, -1.0, 1.0).astype(np.float32)


def colorir(indice: np.ndarray, minimo: float = -1.0, maximo: float = 1.0) -> np.ndarray:
    normalizado = np.clip((indice - minimo) / (maximo - minimo), 0, 1)
    cinza = (normalizado * 255).astype(np.uint8)
    return cv2.applyColorMap(cinza, _LUT)


def gerar_mapa_vari(origem: Path, destino: Path) -> dict:
    bgr = cv2.imread(str(origem), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"Não foi possível abrir a imagem {origem.name}")
    vari = calcular_vari(bgr)
    if not cv2.imwrite(str(destino), colorir(vari)):
        raise ValueError("Falha ao gravar o mapa VARI")
    return {"indice": "VARI", "media": float(vari.mean()), "min": float(vari.min()), "max": float(vari.max())}


def estatisticas_ndvi_geotiff(caminho: Path, preview: Path | None = None) -> dict:
    """Lê o NDVI na banda 1 e usa a banda 3 como máscara do talhão (pixel ≠ 0 = dentro)."""
    with rasterio.open(caminho) as src:
        ndvi = src.read(1).astype(np.float32)
        mascara = src.read(3) != 0 if src.count >= 3 else np.ones_like(ndvi, dtype=bool)
        if src.nodata is not None:
            mascara &= ndvi != src.nodata
    mascara &= np.isfinite(ndvi)
    valores = ndvi[mascara]
    if valores.size == 0:
        raise ValueError("GeoTIFF sem pixels válidos dentro da máscara do talhão")
    if preview is not None:
        img = colorir(ndvi, 0.0, 1.0)
        img[~mascara] = (255, 255, 255)
        cv2.imwrite(str(preview), img)
    return {
        "ndvi_medio": round(float(valores.mean()), 4),
        "ndvi_min": round(float(valores.min()), 4),
        "ndvi_max": round(float(valores.max()), 4),
    }


def _data_da_imagem(img: Imagem) -> date:
    if isinstance(img.data_captura, datetime):
        return img.data_captura.date()
    return img.data_captura or date.today()


def processar_imagem(imagem_id: int) -> None:
    """Executado em segundo plano: abre a própria sessão de banco."""
    db = SessionLocal()
    try:
        img = db.get(Imagem, imagem_id)
        if img is None:
            return
        img.status = StatusImagem.PROCESSANDO
        db.commit()
        try:
            origem = storage.caminho_absoluto(img.caminho)
            if img.tipo in TIPOS_RGB:
                relativo = storage.novo_relativo("processadas", ".png")
                gerar_mapa_vari(origem, storage.caminho_absoluto(relativo))
                img.caminho_processado = relativo
            elif img.tipo == TipoImagem.NDVI_GEOTIFF:
                relativo = storage.novo_relativo("processadas", ".png")
                estat = estatisticas_ndvi_geotiff(origem, storage.caminho_absoluto(relativo))
                img.caminho_processado = relativo
                upsert(
                    db,
                    MetricaTalhao,
                    [{"talhao_id": img.talhao_id, "data": _data_da_imagem(img), **estat}],
                    ("talhao_id", "data"),
                )
            img.status = StatusImagem.PROCESSADO
        except Exception:
            log.exception("Falha ao processar imagem %s", imagem_id)
            db.rollback()
            img = db.get(Imagem, imagem_id)
            img.status = StatusImagem.ERRO
        db.commit()
    finally:
        db.close()
