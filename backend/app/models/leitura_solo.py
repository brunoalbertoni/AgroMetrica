from datetime import date

from sqlalchemy import Date, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class LeituraSolo(Base):
    __tablename__ = "leituras_solo"
    __table_args__ = (UniqueConstraint("talhao_id", "ponto", "data_coleta", name="uq_solo_ponto_data"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    talhao_id: Mapped[int] = mapped_column(ForeignKey("talhoes.id"), index=True)
    zona: Mapped[int | None] = mapped_column(Integer)
    ponto: Mapped[str] = mapped_column(String(40))
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    data_coleta: Mapped[date] = mapped_column(Date)
    ph: Mapped[float | None] = mapped_column(Float)
    mo: Mapped[float | None] = mapped_column(Float)
    ctc: Mapped[float | None] = mapped_column(Float)
    p: Mapped[float | None] = mapped_column(Float)
    k: Mapped[float | None] = mapped_column(Float)
    ca: Mapped[float | None] = mapped_column(Float)
    mg: Mapped[float | None] = mapped_column(Float)
    s: Mapped[float | None] = mapped_column(Float)
    b: Mapped[float | None] = mapped_column(Float)
    zn: Mapped[float | None] = mapped_column(Float)
    mn: Mapped[float | None] = mapped_column(Float)
    cu: Mapped[float | None] = mapped_column(Float)
    v_pct: Mapped[float | None] = mapped_column(Float)
