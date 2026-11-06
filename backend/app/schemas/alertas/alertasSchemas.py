from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.enums import Severidade


class AlertaOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    talhao_id: int
    diagnostico_id: int
    severidade: Severidade
    mensagem: str
    lido: bool
    criado_em: datetime | None
