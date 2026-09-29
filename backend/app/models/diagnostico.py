from datetime import datetime

from sqlalchemy import JSON, DateTime, Float, ForeignKey, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import Severidade, TipoDiagnostico, sa_enum


class Diagnostico(Base):
    __tablename__ = "diagnosticos"

    id: Mapped[int] = mapped_column(primary_key=True)
    imagem_id: Mapped[int | None] = mapped_column(ForeignKey("imagens.id"))
    talhao_id: Mapped[int] = mapped_column(ForeignKey("talhoes.id"), index=True)
    praga_id: Mapped[int | None] = mapped_column(ForeignKey("pragas.id"))
    tipo: Mapped[TipoDiagnostico] = mapped_column(sa_enum(TipoDiagnostico))
    severidade: Mapped[Severidade] = mapped_column(sa_enum(Severidade))
    confianca: Mapped[float | None] = mapped_column(Float)
    detalhes: Mapped[dict | None] = mapped_column(JSON)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    imagem = relationship("Imagem")
    praga = relationship("Praga")
    talhao = relationship("Talhao")
    prescricoes = relationship("Prescricao", back_populates="diagnostico", cascade="all, delete-orphan")
