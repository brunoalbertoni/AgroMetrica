from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.services.assistente import assistenteService as svc

router = APIRouter(prefix="/assistente", tags=["assistente"], dependencies=[Depends(get_current_user)])


class MensagemHistorico(BaseModel):
    papel: str
    texto: str = Field(max_length=8000)


class ChatIn(BaseModel):
    mensagem: str = Field(min_length=1, max_length=2000)
    historico: list[MensagemHistorico] = Field(default_factory=list, max_length=10)


@router.post("/chat")
def chat(entrada: ChatIn, db: Session = Depends(get_db)):
    try:
        resposta, paineis = svc.responder(db, entrada.mensagem, [h.model_dump() for h in entrada.historico])
    except svc.ErroAssistente as erro:
        raise HTTPException(erro.status, str(erro)) from erro
    return {"resposta": resposta, "paineis": paineis}
