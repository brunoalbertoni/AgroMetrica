from datetime import date
from decimal import Decimal

from sqlalchemy import Date, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
from app.models.enums import Finalidade, Sistema, sa_enum


class Talhao(Base):
    __tablename__ = "talhoes"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100))
    area_ha: Mapped[Decimal] = mapped_column(Numeric(8, 2))
    cultura: Mapped[str] = mapped_column(String(60))
    sistema: Mapped[Sistema] = mapped_column(sa_enum(Sistema))
    finalidade: Mapped[Finalidade] = mapped_column(sa_enum(Finalidade))
    # (MySQL) polígono em texto WKT: POLYGON((lon lat, ...))
    geometria: Mapped[str | None] = mapped_column(Text)
    # identificador do talhão no sistema de origem (idField do EKOS)
    codigo_externo: Mapped[str | None] = mapped_column(String(40))
    data_plantio: Mapped[date | None] = mapped_column(Date)
