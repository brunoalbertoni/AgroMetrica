from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import require_role
from app.models import Usuario
from app.models.enums import Perfil
from app.schemas.prescricoes.prescricoesSchemas import PrescricaoOut, PrescricaoPatch
from app.services.prescricoes import prescricoesService as svc

router = APIRouter(prefix="/prescricoes", tags=["prescricoes"])


@router.patch("/{prescricao_id}", response_model=PrescricaoOut)
def alterar(
    prescricao_id: int,
    dados: PrescricaoPatch,
    usuario: Usuario = Depends(require_role(Perfil.AGRONOMO)),
    db: Session = Depends(get_db),
):
    return svc.alterar_status(db, prescricao_id, dados.status, usuario)
