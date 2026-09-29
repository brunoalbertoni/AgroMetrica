from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.models.enums import Perfil


class LoginIn(BaseModel):
    email: str
    senha: str


class UsuarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nome: str
    email: str
    perfil: Perfil
    ativo: bool
    criado_em: datetime | None = None


class LoginOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    usuario: UsuarioOut


class UsuarioCreate(BaseModel):
    nome: str = Field(min_length=1, max_length=100)
    email: EmailStr
    senha: str = Field(min_length=6)
    perfil: Perfil
    ativo: bool = True


class UsuarioUpdate(BaseModel):
    nome: str | None = Field(default=None, min_length=1, max_length=100)
    email: EmailStr | None = None
    senha: str | None = Field(default=None, min_length=6)
    perfil: Perfil | None = None
    ativo: bool | None = None
