from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import get_current_user
from app.models import Imagem, Usuario
from app.models.enums import StatusImagem, TipoImagem
from app.services import imagem as svc
from app.services import storage

router = APIRouter(tags=["imagens"])


class ImagemOut(BaseModel):
    id: int
    talhao_id: int
    tipo: TipoImagem
    status: StatusImagem
    caminho: str
    caminho_processado: str | None
    url: str | None
    url_processada: str | None
    indice: str | None
    data_captura: datetime | None


def imagem_out(img: Imagem) -> ImagemOut:
    return ImagemOut(**svc.representar(img))


@router.post("/imagens", response_model=ImagemOut, status_code=202)
async def enviar(
    background: BackgroundTasks,
    arquivo: UploadFile,
    talhao_id: int = Form(...),
    tipo: TipoImagem = Form(...),
    data_captura: datetime | None = Form(None),
    usuario: Usuario = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    conteudo = await arquivo.read()
    img = svc.receber(db, conteudo, arquivo.filename or "", talhao_id, tipo, data_captura, usuario.id)
    background.add_task(svc.processar_imagem, img.id)
    return imagem_out(img)


@router.get("/imagens/{imagem_id}", response_model=ImagemOut, dependencies=[Depends(get_current_user)])
def obter(imagem_id: int, db: Session = Depends(get_db)):
    img = db.get(Imagem, imagem_id)
    if img is None:
        raise HTTPException(404, "Imagem não encontrada")
    return imagem_out(img)


@router.get("/arquivos/{caminho:path}", include_in_schema=False)
def arquivo(caminho: str):
    # Público de propósito: <img src> não envia o header Authorization; os nomes são UUIDs.
    alvo = storage.resolver_seguro(caminho)
    if alvo is None:
        raise HTTPException(404, "Arquivo não encontrado")
    # nosniff: o navegador respeita o tipo declarado e não executa o arquivo como outra coisa
    return FileResponse(alvo, headers={"X-Content-Type-Options": "nosniff"})
