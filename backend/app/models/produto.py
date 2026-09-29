from sqlalchemy import Float, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import ClasseProduto, sa_enum


class Produto(Base):
    __tablename__ = "produtos"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome_comercial: Mapped[str] = mapped_column(String(120))
    ingrediente_ativo: Mapped[str | None] = mapped_column(String(150))
    classe: Mapped[ClasseProduto] = mapped_column(sa_enum(ClasseProduto))
    dose_min: Mapped[float] = mapped_column(Float)
    dose_max: Mapped[float] = mapped_column(Float)
    unidade: Mapped[str] = mapped_column(String(20))
    carencia_dias: Mapped[int | None] = mapped_column(Integer)
    registro_mapa: Mapped[str | None] = mapped_column(String(40))

    pragas = relationship("Praga", secondary="praga_produto", back_populates="produtos")
