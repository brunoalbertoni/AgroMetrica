from datetime import date

from sqlalchemy import Date, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class OperacaoTalhao(Base):
    """Operação de máquina agregada por talhão (calagem, gessagem, adubação de plantio, plantio),
    a partir das camadas de telemetria do EKOS."""

    __tablename__ = "operacoes_talhao"
    __table_args__ = (UniqueConstraint("talhao_id", "operacao", name="uq_operacao_talhao"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    talhao_id: Mapped[int] = mapped_column(ForeignKey("talhoes.id"), index=True)
    operacao: Mapped[str] = mapped_column(String(60))
    data_inicio: Mapped[date] = mapped_column(Date)
    data_fim: Mapped[date] = mapped_column(Date)
    area_ha: Mapped[float] = mapped_column(Float)
    # média ponderada pela área de cada trecho registrado pela máquina
    dose_aplicada: Mapped[float | None] = mapped_column(Float)
    dose_configurada: Mapped[float | None] = mapped_column(Float)
    unidade: Mapped[str] = mapped_column(String(20))
