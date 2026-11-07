from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


def excluir(db: Session, obj, motivo: str) -> None:
    """Exclui o registro; se outros dados dependem dele, devolve 409 com uma mensagem clara."""
    try:
        db.delete(obj)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, motivo) from None
