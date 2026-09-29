from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import StatusImagem, TipoImagem, sa_enum


class Imagem(Base):
    __tablename__ = "imagens"

    id: Mapped[int] = mapped_column(primary_key=True)
    talhao_id: Mapped[int] = mapped_column(ForeignKey("talhoes.id"), index=True)
    tipo: Mapped[TipoImagem] = mapped_column(sa_enum(TipoImagem))
    caminho: Mapped[str] = mapped_column(String(500))
    caminho_processado: Mapped[str | None] = mapped_column(String(500))
    data_captura: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[StatusImagem] = mapped_column(sa_enum(StatusImagem), default=StatusImagem.PENDENTE)
    enviado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))
