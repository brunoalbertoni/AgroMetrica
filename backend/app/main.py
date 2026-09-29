from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.routers import auth, talhoes, uploads, usuarios

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


for _r in (auth.router, usuarios.router, talhoes.router, uploads.router):
    app.include_router(_r, prefix="/api")
