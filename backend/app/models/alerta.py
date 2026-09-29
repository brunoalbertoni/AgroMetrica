from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import Severidade, sa_enum


class Alerta(Base):
    __tablename__ = "alertas"

    id: Mapped[int] = mapped_column(primary_key=True)
    talhao_id: Mapped[int] = mapped_column(ForeignKey("talhoes.id"), index=True)
    diagnostico_id: Mapped[int] = mapped_column(ForeignKey("diagnosticos.id"))
    severidade: Mapped[Severidade] = mapped_column(sa_enum(Severidade))
    mensagem: Mapped[str] = mapped_column(String(300))
    lido: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    criado_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
