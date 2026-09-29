from fastapi import APIRouter, Depends, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_role
from app.models import Usuario
from app.models.enums import Perfil
from app.schemas.usuario import UsuarioCreate, UsuarioOut, UsuarioUpdate
from app.services import usuarios as svc

router = APIRouter(prefix="/usuarios", tags=["usuarios"], dependencies=[Depends(require_role(Perfil.ADMIN))])


@router.get("", response_model=list[UsuarioOut])
def listar(db: Session = Depends(get_db)):
    return db.scalars(select(Usuario).order_by(Usuario.id)).all()


@router.get("/{usuario_id}", response_model=UsuarioOut)
def obter(usuario_id: int, db: Session = Depends(get_db)):
    return svc.obter(db, usuario_id)


@router.post("", response_model=UsuarioOut, status_code=201)
def criar(dados: UsuarioCreate, db: Session = Depends(get_db)):
    return svc.criar(db, dados)


@router.patch("/{usuario_id}", response_model=UsuarioOut)
def atualizar(usuario_id: int, dados: UsuarioUpdate, db: Session = Depends(get_db)):
    return svc.atualizar(db, usuario_id, dados)


@router.delete("/{usuario_id}", status_code=204)
def remover(usuario_id: int, db: Session = Depends(get_db)):
    svc.remover(db, usuario_id)
    return Response(status_code=204)
