"""mensagens do caderno de campo

Revision ID: a1c4e7d90b23
Revises: f79b9cf8743b
Create Date: 2026-11-07 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1c4e7d90b23'
down_revision: Union[str, Sequence[str], None] = 'f79b9cf8743b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

CATEGORIAS = ('SOLO', 'PRAGA', 'CLIMA', 'MANEJO', 'OBSERVACAO', 'OUTROS')
DESTINOS = ('CAIXA_DE_ENTRADA', 'ANOTACAO', 'DADO_SOLO', 'DESCARTADA')


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('mensagens_campo',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('origem', sa.String(length=20), nullable=False),
    sa.Column('remetente', sa.String(length=80), nullable=False),
    sa.Column('texto', sa.Text(), nullable=False),
    sa.Column('recebido_em', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
    sa.Column('categoria', sa.Enum(*CATEGORIAS, name='categoriacampo'), nullable=False),
    sa.Column('classificada_por_ia', sa.Boolean(), nullable=False),
    sa.Column('resumo', sa.String(length=200), nullable=True),
    sa.Column('talhao_id', sa.Integer(), nullable=True),
    sa.Column('destino', sa.Enum(*DESTINOS, name='destinocampo'), nullable=False),
    sa.Column('nota', sa.Text(), nullable=True),
    sa.Column('analise_ia', sa.Text(), nullable=True),
    sa.Column('atualizado_em', sa.DateTime(), nullable=True),
    sa.Column('decidido_por', sa.Integer(), nullable=True),
    sa.ForeignKeyConstraint(['decidido_por'], ['usuarios.id'], ondelete='SET NULL'),
    sa.ForeignKeyConstraint(['talhao_id'], ['talhoes.id'], ondelete='SET NULL'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_mensagens_campo_categoria'), 'mensagens_campo', ['categoria'], unique=False)
    op.create_index(op.f('ix_mensagens_campo_destino'), 'mensagens_campo', ['destino'], unique=False)
    op.create_index(op.f('ix_mensagens_campo_recebido_em'), 'mensagens_campo', ['recebido_em'], unique=False)
    op.create_index(op.f('ix_mensagens_campo_talhao_id'), 'mensagens_campo', ['talhao_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_mensagens_campo_talhao_id'), table_name='mensagens_campo')
    op.drop_index(op.f('ix_mensagens_campo_recebido_em'), table_name='mensagens_campo')
    op.drop_index(op.f('ix_mensagens_campo_destino'), table_name='mensagens_campo')
    op.drop_index(op.f('ix_mensagens_campo_categoria'), table_name='mensagens_campo')
    op.drop_table('mensagens_campo')
