from pydantic import BaseModel, ConfigDict, Field, computed_field

from app.models.enums import ClasseProduto
from app.schemas.pragas.pragasSchemas import PragaOut


class ProdutoCreate(BaseModel):
    nome_comercial: str = Field(min_length=1, max_length=120)
    ingrediente_ativo: str | None = None
    classe: ClasseProduto
    dose_min: float = Field(ge=0)
    dose_max: float = Field(ge=0)
    unidade: str = Field(min_length=1, max_length=20)
    carencia_dias: int | None = Field(default=None, ge=0)
    registro_mapa: str | None = None
    praga_ids: list[int] = []


class ProdutoUpdate(BaseModel):
    nome_comercial: str | None = Field(default=None, min_length=1, max_length=120)
    ingrediente_ativo: str | None = None
    classe: ClasseProduto | None = None
    dose_min: float | None = Field(default=None, ge=0)
    dose_max: float | None = Field(default=None, ge=0)
    unidade: str | None = Field(default=None, min_length=1, max_length=20)
    carencia_dias: int | None = Field(default=None, ge=0)
    registro_mapa: str | None = None
    praga_ids: list[int] | None = None


class ProdutoOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome_comercial: str
    ingrediente_ativo: str | None
    classe: ClasseProduto
    dose_min: float
    dose_max: float
    unidade: str
    carencia_dias: int | None
    registro_mapa: str | None
    pragas: list[PragaOut] = Field(default=[], exclude=True)

    @computed_field
    @property
    def praga_ids(self) -> list[int]:
        return sorted(p.id for p in self.pragas)
