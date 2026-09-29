from sqlalchemy import Column, ForeignKey, Table

from app.core.database import Base

praga_produto = Table(
    "praga_produto",
    Base.metadata,
    Column("praga_id", ForeignKey("pragas.id", ondelete="CASCADE"), primary_key=True),
    Column("produto_id", ForeignKey("produtos.id", ondelete="CASCADE"), primary_key=True),
)
