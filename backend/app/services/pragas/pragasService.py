from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.comum.exclusao import excluir
from app.models import Praga
from app.schemas.pragas.pragasSchemas import PragaCreate, PragaUpdate


def _checar_limiares(p: Praga) -> None:
    if not (p.limiar_alerta <= p.limiar_controle <= p.limiar_dano):
        raise HTTPException(400, "Limiares devem obedecer alerta ≤ controle ≤ dano")


def listar_pragas(db: Session) -> list[Praga]:
    return list(db.scalars(select(Praga).order_by(Praga.nome)))


def obter_praga(db: Session, praga_id: int) -> Praga:
    praga = db.get(Praga, praga_id)
    if praga is None:
        raise HTTPException(404, "Praga não encontrado")
    return praga


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
    excluir(db, obter_praga(db, praga_id), "Praga tem diagnósticos registrados e não pode ser excluída")
