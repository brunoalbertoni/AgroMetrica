from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import TipoUpload, sa_enum


class Upload(Base):
    __tablename__ = "uploads"

    id: Mapped[int] = mapped_column(primary_key=True)
    usuario_id: Mapped[int] = mapped_column(ForeignKey("usuarios.id"))
    nome_arquivo: Mapped[str] = mapped_column(String(255))
    tipo: Mapped[TipoUpload] = mapped_column(sa_enum(TipoUpload))
    linhas_ok: Mapped[int] = mapped_column(Integer, default=0)
    linhas_erro: Mapped[int] = mapped_column(Integer, default=0)
    erros: Mapped[list | None] = mapped_column(JSON)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
