"""Leitura para qualquer usuário logado; escrita só para ADMIN."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.enums import Perfil
from app.schemas.catalogo import PragaCreate, PragaOut, PragaUpdate
from app.services import catalogo as svc

router = APIRouter(tags=["pragas"])
_leitura = [Depends(get_current_user)]
_escrita = [Depends(require_role(Perfil.ADMIN))]


@router.get("/pragas", response_model=list[PragaOut], dependencies=_leitura)
def listar_pragas(db: Session = Depends(get_db)):
    return svc.listar_pragas(db)


@router.get("/pragas/{praga_id}", response_model=PragaOut, dependencies=_leitura)
def obter_praga(praga_id: int, db: Session = Depends(get_db)):
    return svc.obter_praga(db, praga_id)


@router.post("/pragas", response_model=PragaOut, status_code=201, dependencies=_escrita)
def criar_praga(dados: PragaCreate, db: Session = Depends(get_db)):
    return svc.criar_praga(db, dados)


@router.patch("/pragas/{praga_id}", response_model=PragaOut, dependencies=_escrita)
def atualizar_praga(praga_id: int, dados: PragaUpdate, db: Session = Depends(get_db)):
    return svc.atualizar_praga(db, praga_id, dados)


@router.delete("/pragas/{praga_id}", status_code=204, dependencies=_escrita)
def remover_praga(praga_id: int, db: Session = Depends(get_db)):
    svc.remover_praga(db, praga_id)
    return Response(status_code=204)
