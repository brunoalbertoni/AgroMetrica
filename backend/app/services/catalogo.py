from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Praga, Produto
from app.schemas.catalogo import PragaCreate, PragaUpdate, ProdutoCreate, ProdutoUpdate


def _obter(db: Session, modelo, item_id: int, nome: str):
    obj = db.get(modelo, item_id)
    if obj is None:
        raise HTTPException(404, f"{nome} não encontrado")
    return obj


def _checar_limiares(p: Praga) -> None:
    if not (p.limiar_alerta <= p.limiar_controle <= p.limiar_dano):
        raise HTTPException(400, "Limiares devem obedecer alerta ≤ controle ≤ dano")


def _checar_doses(p: Produto) -> None:
    if p.dose_min > p.dose_max:
        raise HTTPException(400, "dose_min não pode ser maior que dose_max")


def _pragas(db: Session, ids: list[int]) -> list[Praga]:
    pragas = list(db.scalars(select(Praga).where(Praga.id.in_(ids)))) if ids else []
    if len(pragas) != len(set(ids)):
        raise HTTPException(400, "praga_ids contém praga inexistente")
    return pragas


def listar_pragas(db: Session) -> list[Praga]:
    return list(db.scalars(select(Praga).order_by(Praga.nome)))


def obter_praga(db: Session, praga_id: int) -> Praga:
    return _obter(db, Praga, praga_id, "Praga")


def criar_praga(db: Session, dados: PragaCreate) -> Praga:
    p = Praga(**dados.model_dump())
    _checar_limiares(p)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def atualizar_praga(db: Session, praga_id: int, dados: PragaUpdate) -> Praga:
    p = obter_praga(db, praga_id)
    for campo, valor in dados.model_dump(exclude_unset=True).items():
        setattr(p, campo, valor)
    _checar_limiares(p)
    db.commit()
    db.refresh(p)
    return p


def remover_praga(db: Session, praga_id: int) -> None:
    db.delete(obter_praga(db, praga_id))
    db.commit()


def listar_produtos(db: Session) -> list[Produto]:
    return list(db.scalars(select(Produto).order_by(Produto.nome_comercial)))


def obter_produto(db: Session, produto_id: int) -> Produto:
    return _obter(db, Produto, produto_id, "Produto")


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
    db.delete(obter_produto(db, produto_id))
    db.commit()
