from datetime import date

from pydantic import BaseModel, ConfigDict

from app.models.enums import Finalidade, Sistema


class MetricaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    data: date
    ndvi_medio: float | None
    ndvi_min: float | None
    ndvi_max: float | None
    balanco_hidrico_mm: float | None
    produtividade_kg_ha: float | None


class TalhaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    area_ha: float
    cultura: str
    sistema: Sistema
    finalidade: Finalidade
    geometria: str | None = None
    data_plantio: date | None = None
    ultima_metrica: MetricaOut | None = None


class OperacaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    operacao: str
    data_inicio: date
    data_fim: date
    area_ha: float
    dose_aplicada: float | None
    dose_configurada: float | None
    unidade: str


class TalhaoPagina(BaseModel):
    items: list[TalhaoOut]
    total: int
    page: int
    size: int


class SoloOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    zona: int | None
    ponto: str
    lat: float | None
    lon: float | None
    data_coleta: date
    ph: float | None
    mo: float | None
    ctc: float | None
    p: float | None
    k: float | None
    ca: float | None
    mg: float | None
    s: float | None
    b: float | None
    zn: float | None
    mn: float | None
    cu: float | None
    v_pct: float | None
    classificacao: dict[str, str] = {}


class ClimaDiaOut(BaseModel):
    data: date
    temp_min: float | None
    temp_med: float | None
    temp_max: float | None
    chuva_mm: float | None
    umidade_med: float | None
    vento_kmh: float | None
    radiacao: float | None
    etp_mm: float | None
