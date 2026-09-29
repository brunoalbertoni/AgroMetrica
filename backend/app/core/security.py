from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models import Usuario
from app.models.enums import Perfil

ALGORITMO = "HS256"
_pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
_bearer = HTTPBearer(auto_error=False)


def hash_senha(senha: str) -> str:
    return _pwd.hash(senha)


def verificar_senha(senha: str, senha_hash: str) -> bool:
    return _pwd.verify(senha, senha_hash)


def criar_token(usuario_id: int, perfil: str) -> str:
    expira = datetime.now(UTC) + timedelta(minutes=settings.jwt_expires_min)
    return jwt.encode(
        {"sub": str(usuario_id), "perfil": perfil, "exp": expira}, settings.jwt_secret, ALGORITMO
    )


def get_current_user(
    cred: HTTPAuthorizationCredentials | None = Depends(_bearer), db: Session = Depends(get_db)
) -> Usuario:
    nao_autenticado = HTTPException(
        status.HTTP_401_UNAUTHORIZED, "Não autenticado", headers={"WWW-Authenticate": "Bearer"}
    )
    if cred is None:
        raise nao_autenticado
    try:
        payload = jwt.decode(cred.credentials, settings.jwt_secret, algorithms=[ALGORITMO])
        usuario_id = int(payload["sub"])
    except (JWTError, KeyError, ValueError):
        raise nao_autenticado from None
    usuario = db.get(Usuario, usuario_id)
    if usuario is None or not usuario.ativo:
        raise nao_autenticado
    return usuario


def require_role(*perfis: Perfil):
    """Dependência que exige um dos perfis. ADMIN sempre passa (é superconjunto de AGRONOMO)."""

    def _checar(usuario: Usuario = Depends(get_current_user)) -> Usuario:
        if usuario.perfil != Perfil.ADMIN and usuario.perfil not in perfis:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Sem permissão para esta operação")
        return usuario

    return _checar
