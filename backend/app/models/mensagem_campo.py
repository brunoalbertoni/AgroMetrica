from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.enums import CategoriaCampo, DestinoCampo, sa_enum


class MensagemCampo(Base):
    """Mensagem informal do agrônomo (hoje digitada na tela; depois vinda do WhatsApp)."""

    __tablename__ = "mensagens_campo"

    id: Mapped[int] = mapped_column(primary_key=True)
    origem: Mapped[str] = mapped_column(String(20), default="manual")  # 'manual' | 'whatsapp'
    remetente: Mapped[str] = mapped_column(String(80), default="")
    texto: Mapped[str] = mapped_column(Text)
    recebido_em: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)
    categoria: Mapped[CategoriaCampo] = mapped_column(sa_enum(CategoriaCampo), index=True)
    classificada_por_ia: Mapped[bool] = mapped_column(Boolean, default=False)
    resumo: Mapped[str | None] = mapped_column(String(200))
    talhao_id: Mapped[int | None] = mapped_column(ForeignKey("talhoes.id", ondelete="SET NULL"), index=True)
    destino: Mapped[DestinoCampo] = mapped_column(
        sa_enum(DestinoCampo), default=DestinoCampo.CAIXA_DE_ENTRADA, index=True
    )
    nota: Mapped[str | None] = mapped_column(Text)
    analise_ia: Mapped[str | None] = mapped_column(Text)
    atualizado_em: Mapped[datetime | None] = mapped_column(DateTime)
    decidido_por: Mapped[int | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))

    talhao = relationship("Talhao")
