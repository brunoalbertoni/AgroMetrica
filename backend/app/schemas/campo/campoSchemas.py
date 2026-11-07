from datetime import datetime

from pydantic import BaseModel, Field

from app.models.enums import CategoriaCampo, DestinoCampo


class MensagemIn(BaseModel):
    texto: str = Field(min_length=1, max_length=4000)
    remetente: str | None = Field(default=None, max_length=80)
    talhao_id: int | None = None


class MensagemPatch(BaseModel):
    """Decisão do usuário. Só os campos enviados mudam; talhao_id null limpa o vínculo."""

    categoria: CategoriaCampo | None = None
    talhao_id: int | None = None
    destino: DestinoCampo | None = None
    nota: str | None = Field(default=None, max_length=2000)


class MensagemOut(BaseModel):
    id: int
    origem: str
    remetente: str
    texto: str
    recebido_em: datetime | None
    categoria: CategoriaCampo
    classificada_por_ia: bool
    resumo: str | None
    talhao_id: int | None
    talhao_nome: str | None
    destino: DestinoCampo
    nota: str | None
    analise_ia: str | None
    atualizado_em: datetime | None


class ContagemCategoria(BaseModel):
    categoria: CategoriaCampo
    total: int
    pendentes: int


class ResumoCampo(BaseModel):
    pendentes: int
    total: int
    categorias: list[ContagemCategoria]
