from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.enums import Perfil, Severidade, TipoDiagnostico
from app.schemas.diagnostico import ArmadilhaIn, DiagnosticoDetalhe, DiagnosticoOut
from app.services import diagnostico as svc

router = APIRouter(prefix="/diagnosticos", tags=["diagnosticos"])


@router.get("", response_model=list[DiagnosticoOut], dependencies=[Depends(get_current_user)])
def listar(
    talhao_id: int | None = None,
    severidade: Severidade | None = None,
    tipo: TipoDiagnostico | None = None,
    db: Session = Depends(get_db),
):
    return svc.listar(db, talhao_id, severidade, tipo)


@router.get("/{diagnostico_id}", response_model=DiagnosticoDetalhe, dependencies=[Depends(get_current_user)])
def detalhar(diagnostico_id: int, db: Session = Depends(get_db)):
    return svc.detalhar(db, diagnostico_id)


@router.post(
    "/rodar/{talhao_id}",
    response_model=list[DiagnosticoOut],
    dependencies=[Depends(require_role(Perfil.AGRONOMO))],
)
def rodar(talhao_id: int, db: Session = Depends(get_db)):
    return [svc.representar(db, d) for d in svc.rodar(db, talhao_id)]


@router.post(
    "/armadilha",
    response_model=DiagnosticoOut | None,
    dependencies=[Depends(require_role(Perfil.AGRONOMO))],
)
def armadilha(dados: ArmadilhaIn, db: Session = Depends(get_db)):
    """Registra uma leitura de armadilha. Devolve null se a contagem não atingir o limiar de alerta."""
    from datetime import datetime

    diag = svc.registrar_armadilha(
        db,
        dados.talhao_id,
        dados.praga_id,
        dados.contagem,
        dados.data or datetime.now(),
        imagem_id=dados.imagem_id,
        bboxes=[b.model_dump() for b in dados.bboxes],
    )
    return svc.representar(db, diag) if diag else None
