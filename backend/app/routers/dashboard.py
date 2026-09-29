from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.services import dashboard as svc

router = APIRouter(tags=["dashboard"], dependencies=[Depends(get_current_user)])


@router.get("/dashboard/resumo")
def resumo(db: Session = Depends(get_db)):
    """Cards, série de NDVI por talhão e severidade dos alertas abertos por talhão (para o mapa)."""
    return svc.resumo(db)


@router.get("/comparativo")
def comparativo(
    a: int = Query(..., description="id do talhão A (ex.: Grão 4.0)"),
    b: int = Query(..., description="id do talhão B (ex.: Convencional)"),
    db: Session = Depends(get_db),
):
    """Séries lado a lado de NDVI, produtividade, pragas e clima, com os eventos (diagnósticos)."""
    return svc.comparativo(db, a, b)
