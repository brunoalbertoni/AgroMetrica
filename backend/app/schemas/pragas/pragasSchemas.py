from pydantic import BaseModel, ConfigDict, Field


class PragaCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    nome_cientifico: str | None = None
    cultura: str | None = None
    limiar_alerta: float = Field(ge=0)
    limiar_controle: float = Field(ge=0)
    limiar_dano: float = Field(ge=0)


class PragaUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=100)
    nome_cientifico: str | None = None
    cultura: str | None = None
    limiar_alerta: float | None = Field(default=None, ge=0)
    limiar_controle: float | None = Field(default=None, ge=0)
    limiar_dano: float | None = Field(default=None, ge=0)


class PragaOut(PragaCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int
