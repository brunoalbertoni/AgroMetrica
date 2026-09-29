from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from app.core.config import settings

_sqlite = settings.database_url.startswith("sqlite")
_connect_args = {"check_same_thread": False} if _sqlite else {}
engine = create_engine(settings.database_url, pool_pre_ping=True, connect_args=_connect_args)

if _sqlite:
    # SQLite ignora FKs por padrão; ligando, os testes se comportam como o MySQL.
    @event.listens_for(engine, "connect")
    def _ligar_fks(conexao, _registro):
        conexao.execute("PRAGMA foreign_keys=ON")


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
