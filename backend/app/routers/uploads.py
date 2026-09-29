from fastapi import APIRouter, Depends, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Usuario
from app.models.enums import TipoUpload
from app.services import ingestao

router = APIRouter(prefix="/uploads", tags=["uploads"])


class ErroLinha(BaseModel):
    linha: int
    erro: str


class UploadOut(BaseModel):
    linhas_ok: int
    linhas_erro: int
    erros: list[ErroLinha]


@router.post("/{tipo}", response_model=UploadOut)
async def enviar(
    tipo: str,
    arquivo: UploadFile,
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        tipo_upload = TipoUpload(tipo.upper())
    except ValueError:
        validos = ", ".join(t.value.lower() for t in TipoUpload)
        raise HTTPException(400, f"Tipo de upload inválido: {tipo}. Use: {validos}") from None
    conteudo = await arquivo.read()
    return ingestao.importar(db, tipo_upload, conteudo, arquivo.filename or "arquivo.csv", usuario.id)
