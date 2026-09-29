from datetime import datetime

from sqlalchemy import DateTime, Float
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LeituraClima(Base):
    __tablename__ = "leituras_clima"

    id: Mapped[int] = mapped_column(primary_key=True)
    data_hora: Mapped[datetime] = mapped_column(DateTime, unique=True, index=True)
    temp_min: Mapped[float | None] = mapped_column(Float)
    temp_med: Mapped[float | None] = mapped_column(Float)
    temp_max: Mapped[float | None] = mapped_column(Float)
    chuva_mm: Mapped[float | None] = mapped_column(Float)
    umidade_med: Mapped[float | None] = mapped_column(Float)
    vento_kmh: Mapped[float | None] = mapped_column(Float)
    radiacao: Mapped[float | None] = mapped_column(Float)
    etp_mm: Mapped[float | None] = mapped_column(Float)
