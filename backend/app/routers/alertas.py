from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.schemas.diagnostico import AlertaOut
from app.services import alertas as svc

router = APIRouter(prefix="/alertas", tags=["alertas"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=list[AlertaOut])
def listar(lido: bool | None = None, db: Session = Depends(get_db)):
    return svc.listar(db, lido)


@router.patch("/{alerta_id}/lido", response_model=AlertaOut)
def marcar_lido(alerta_id: int, db: Session = Depends(get_db)):
    return svc.marcar_lido(db, alerta_id)
