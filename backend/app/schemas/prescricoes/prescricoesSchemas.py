from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import StatusPrescricao
from app.schemas.produtos.produtosSchemas import ProdutoOut


class PrescricaoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    diagnostico_id: int
    produto: ProdutoOut
    dose: float
    unidade: str
    janela_inicio: datetime | None
    janela_fim: datetime | None
    status: StatusPrescricao
    aprovado_por: int | None


class PrescricaoPatch(BaseModel):
    status: StatusPrescricao
