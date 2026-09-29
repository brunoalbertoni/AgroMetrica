from sqlalchemy import Float, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base


class Praga(Base):
    __tablename__ = "pragas"

    id: Mapped[int] = mapped_column(primary_key=True)
    nome: Mapped[str] = mapped_column(String(100))
    nome_cientifico: Mapped[str | None] = mapped_column(String(150))
    cultura: Mapped[str | None] = mapped_column(String(60))
    limiar_alerta: Mapped[float] = mapped_column(Float)
    limiar_controle: Mapped[float] = mapped_column(Float)
    limiar_dano: Mapped[float] = mapped_column(Float)

    produtos = relationship("Produto", secondary="praga_produto", back_populates="pragas")
