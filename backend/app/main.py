from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.controllers.alertas import alertasController as alertas
from app.controllers.assistente import assistenteController as assistente
from app.controllers.auth import authController as auth
from app.controllers.campo import campoController as campo
from app.controllers.dashboard import dashboardController as dashboard
from app.controllers.diagnosticos import diagnosticosController as diagnosticos
from app.controllers.imagens import imagensController as imagens
from app.controllers.pragas import pragasController as pragas
from app.controllers.prescricoes import prescricoesController as prescricoes
from app.controllers.produtos import produtosController as produtos
from app.controllers.talhoes import talhoesController as talhoes
from app.controllers.uploads import uploadsController as uploads
from app.controllers.usuarios import usuariosController as usuarios
from app.core.config import settings

app = FastAPI(title="AgroMétrica API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(RequestValidationError)
async def _validacao_400(_: Request, exc: RequestValidationError):
    """Padroniza erros de validação em 400 com {"detail": "mensagem"}."""
    partes = []
    for erro in exc.errors():
        campo = ".".join(str(p) for p in erro.get("loc", []) if p not in ("body", "query", "path"))
        partes.append(f"{campo}: {erro.get('msg')}" if campo else str(erro.get("msg")))
    return JSONResponse(status_code=400, content={"detail": "; ".join(partes) or "Dados inválidos"})


@app.get("/api/health")
def health():
    return {"status": "ok"}


_ROUTERS = (
    auth.router,
    usuarios.router,
    talhoes.router,
    uploads.router,
    imagens.router,
    diagnosticos.router,
    pragas.router,
    produtos.router,
    prescricoes.router,
    alertas.router,
    dashboard.router,
    assistente.router,
    campo.router,
)
for _r in _ROUTERS:
    app.include_router(_r, prefix="/api")
