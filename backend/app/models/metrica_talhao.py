from datetime import date

from sqlalchemy import Date, Float, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class MetricaTalhao(Base):
    __tablename__ = "metricas_talhao"
    __table_args__ = (UniqueConstraint("talhao_id", "data", name="uq_metrica_talhao_data"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    talhao_id: Mapped[int] = mapped_column(ForeignKey("talhoes.id"), index=True)
    data: Mapped[date] = mapped_column(Date)
    ndvi_medio: Mapped[float | None] = mapped_column(Float)
    ndvi_min: Mapped[float | None] = mapped_column(Float)
    ndvi_max: Mapped[float | None] = mapped_column(Float)
    balanco_hidrico_mm: Mapped[float | None] = mapped_column(Float)
    produtividade_kg_ha: Mapped[float | None] = mapped_column(Float)
