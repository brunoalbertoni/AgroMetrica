from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import StatusPrescricao, sa_enum


class Prescricao(Base):
    __tablename__ = "prescricoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    diagnostico_id: Mapped[int] = mapped_column(ForeignKey("diagnosticos.id"), index=True)
    produto_id: Mapped[int] = mapped_column(ForeignKey("produtos.id"))
    dose: Mapped[float] = mapped_column(Float)
    unidade: Mapped[str] = mapped_column(String(20))
    janela_inicio: Mapped[datetime | None] = mapped_column(DateTime)
    janela_fim: Mapped[datetime | None] = mapped_column(DateTime)
    status: Mapped[StatusPrescricao] = mapped_column(
        sa_enum(StatusPrescricao), default=StatusPrescricao.SUGERIDA
    )
    aprovado_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id"))

    diagnostico = relationship("Diagnostico", back_populates="prescricoes")
    produto = relationship("Produto")
