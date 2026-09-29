from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import criar_token, hash_senha, verificar_senha
from app.models import Usuario
from app.schemas.usuario import UsuarioCreate, UsuarioUpdate


def autenticar(db: Session, email: str, senha: str) -> tuple[str, Usuario]:
    usuario = db.scalar(select(Usuario).where(Usuario.email == email.strip().lower()))
    if usuario is None or not usuario.ativo or not verificar_senha(senha, usuario.senha_hash):
        raise HTTPException(401, "E-mail ou senha inválidos")
    return criar_token(usuario.id, usuario.perfil.value), usuario


def obter(db: Session, usuario_id: int) -> Usuario:
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise HTTPException(404, "Usuário não encontrado")
    return usuario


def _email_livre(db: Session, email: str, exceto_id: int | None = None) -> None:
    existente = db.scalar(select(Usuario).where(Usuario.email == email))
    if existente is not None and existente.id != exceto_id:
        raise HTTPException(400, "E-mail já cadastrado")


def criar(db: Session, dados: UsuarioCreate) -> Usuario:
    email = dados.email.lower()
    _email_livre(db, email)
    usuario = Usuario(
        nome=dados.nome,
        email=email,
        senha_hash=hash_senha(dados.senha),
        perfil=dados.perfil,
        ativo=dados.ativo,
    )
    db.add(usuario)
    db.commit()
    db.refresh(usuario)
    return usuario


def atualizar(db: Session, usuario_id: int, dados: UsuarioUpdate) -> Usuario:
    usuario = obter(db, usuario_id)
    campos = dados.model_dump(exclude_unset=True)
    if "email" in campos:
        campos["email"] = campos["email"].lower()
        _email_livre(db, campos["email"], usuario_id)
    if "senha" in campos:
        usuario.senha_hash = hash_senha(campos.pop("senha"))
    for campo, valor in campos.items():
        setattr(usuario, campo, valor)
    db.commit()
    db.refresh(usuario)
    return usuario


def remover(db: Session, usuario_id: int) -> None:
    db.delete(obter(db, usuario_id))
    db.commit()
