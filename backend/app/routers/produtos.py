"""Leitura para qualquer usuário logado; escrita só para ADMIN."""

from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.enums import Perfil
from app.schemas.catalogo import ProdutoCreate, ProdutoOut, ProdutoUpdate
from app.services import catalogo as svc

router = APIRouter(tags=["produtos"])
_leitura = [Depends(get_current_user)]
_escrita = [Depends(require_role(Perfil.ADMIN))]


@router.get("/produtos", response_model=list[ProdutoOut], dependencies=_leitura)
def listar_produtos(db: Session = Depends(get_db)):
    return svc.listar_produtos(db)


@router.get("/produtos/{produto_id}", response_model=ProdutoOut, dependencies=_leitura)
def obter_produto(produto_id: int, db: Session = Depends(get_db)):
    return svc.obter_produto(db, produto_id)


@router.post("/produtos", response_model=ProdutoOut, status_code=201, dependencies=_escrita)
def criar_produto(dados: ProdutoCreate, db: Session = Depends(get_db)):
    return svc.criar_produto(db, dados)


@router.patch("/produtos/{produto_id}", response_model=ProdutoOut, dependencies=_escrita)
def atualizar_produto(produto_id: int, dados: ProdutoUpdate, db: Session = Depends(get_db)):
    return svc.atualizar_produto(db, produto_id, dados)


@router.delete("/produtos/{produto_id}", status_code=204, dependencies=_escrita)
def remover_produto(produto_id: int, db: Session = Depends(get_db)):
    svc.remover_produto(db, produto_id)
    return Response(status_code=204)
