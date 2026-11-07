from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.models.enums import Severidade, TipoDiagnostico
from app.schemas.prescricoes.prescricoesSchemas import PrescricaoOut


class BBox(BaseModel):
    """Coordenadas normalizadas de 0 a 1 em relação à imagem original."""

    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(ge=0, le=1)
    h: float = Field(ge=0, le=1)
    rotulo: str | None = None
    confianca: float | None = None


class DiagnosticoOut(BaseModel):
    id: int
    talhao_id: int
    talhao_nome: str | None
    imagem_id: int | None
    praga_id: int | None
    praga_nome: str | None
    tipo: TipoDiagnostico
    severidade: Severidade
    confianca: float | None
    criado_em: datetime | None
    resumo: str


class DiagnosticoDetalhe(DiagnosticoOut):
    detalhes: dict
    bboxes: list[BBox]
    imagem: dict | None
    prescricoes: list[PrescricaoOut]


class ArmadilhaIn(BaseModel):
    talhao_id: int
    praga_id: int
    contagem: float = Field(ge=0)
    data: datetime | None = None
    imagem_id: int | None = None
    bboxes: list[BBox] = []

    @field_validator("data")
    @classmethod
    def _sem_fuso(cls, v: datetime | None) -> datetime | None:
        # o banco guarda horários locais sem fuso; "…Z" vira o horário local equivalente
        return v.astimezone().replace(tzinfo=None) if v is not None and v.tzinfo else v
