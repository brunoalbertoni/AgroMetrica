from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.comum.exclusao import excluir
from app.models import Praga, Produto
from app.schemas.produtos.produtosSchemas import ProdutoCreate, ProdutoUpdate


def _checar_doses(p: Produto) -> None:
    if p.dose_min > p.dose_max:
        raise HTTPException(400, "dose_min não pode ser maior que dose_max")


def _pragas(db: Session, ids: list[int]) -> list[Praga]:
    pragas = list(db.scalars(select(Praga).where(Praga.id.in_(ids)))) if ids else []
    if len(pragas) != len(set(ids)):
        raise HTTPException(400, "praga_ids contém praga inexistente")
    return pragas


def listar_produtos(db: Session) -> list[Produto]:
    return list(db.scalars(select(Produto).order_by(Produto.nome_comercial)))


def obter_produto(db: Session, produto_id: int) -> Produto:
    produto = db.get(Produto, produto_id)
    if produto is None:
        raise HTTPException(404, "Produto não encontrado")
    return produto


def criar_produto(db: Session, dados: ProdutoCreate) -> Produto:
    campos = dados.model_dump(exclude={"praga_ids"})
    p = Produto(**campos)
    _checar_doses(p)
    p.pragas = _pragas(db, dados.praga_ids)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def atualizar_produto(db: Session, produto_id: int, dados: ProdutoUpdate) -> Produto:
    p = obter_produto(db, produto_id)
    campos = dados.model_dump(exclude_unset=True)
    if "praga_ids" in campos:
        p.pragas = _pragas(db, campos.pop("praga_ids") or [])
    for campo, valor in campos.items():
        setattr(p, campo, valor)
    _checar_doses(p)
    db.commit()
    db.refresh(p)
    return p


def remover_produto(db: Session, produto_id: int) -> None:
    excluir(db, obter_produto(db, produto_id), "Produto já aparece em prescrições e não pode ser excluído")
