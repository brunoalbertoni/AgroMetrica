from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Usuario
from app.models.enums import CategoriaCampo, DestinoCampo
from app.schemas.campo.campoSchemas import MensagemIn, MensagemOut, MensagemPatch, ResumoCampo
from app.services.assistente import assistenteService
from app.services.campo import campoService as svc

router = APIRouter(prefix="/campo", tags=["campo"], dependencies=[Depends(get_current_user)])


@router.get("/resumo", response_model=ResumoCampo)
def resumo(db: Session = Depends(get_db)):
    return svc.resumo(db)


@router.get("/mensagens", response_model=list[MensagemOut])
def listar(
    categoria: CategoriaCampo | None = None,
    destino: DestinoCampo | None = None,
    talhao_id: int | None = None,
    db: Session = Depends(get_db),
):
    return [svc.representar(m) for m in svc.listar(db, categoria, destino, talhao_id)]


@router.post("/mensagens", response_model=MensagemOut, status_code=201)
def criar(entrada: MensagemIn, db: Session = Depends(get_db), usuario: Usuario = Depends(get_current_user)):
    """Registra uma mensagem (hoje digitada na tela; o webhook do WhatsApp usará o mesmo serviço)."""
    mensagem = svc.criar(db, entrada.texto, entrada.remetente or usuario.nome, entrada.talhao_id)
    return svc.representar(mensagem)


@router.patch("/mensagens/{mensagem_id}", response_model=MensagemOut)
def decidir(
    mensagem_id: int,
    entrada: MensagemPatch,
    db: Session = Depends(get_db),
    usuario: Usuario = Depends(get_current_user),
):
    mensagem = svc.atualizar(db, mensagem_id, usuario, entrada.model_dump(exclude_unset=True))
    return svc.representar(mensagem)


@router.post("/mensagens/{mensagem_id}/analisar", response_model=MensagemOut)
def analisar(mensagem_id: int, db: Session = Depends(get_db)):
    try:
        return svc.representar(svc.analisar(db, mensagem_id))
    except assistenteService.ErroAssistente as erro:
        raise HTTPException(erro.status, str(erro)) from erro
