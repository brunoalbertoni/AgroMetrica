import uuid
from pathlib import Path

from app.core.config import settings


def raiz() -> Path:
    p = settings.storage_path
    p.mkdir(parents=True, exist_ok=True)
    return p


def salvar(conteudo: bytes, subdir: str, nome_original: str) -> str:
    """Grava o arquivo com nome aleatório e devolve o caminho relativo ao STORAGE_DIR."""
    extensao = Path(nome_original).suffix.lower() or ".bin"
    destino_dir = raiz() / subdir
    destino_dir.mkdir(parents=True, exist_ok=True)
    nome = f"{uuid.uuid4().hex}{extensao}"
    (destino_dir / nome).write_bytes(conteudo)
    return f"{subdir}/{nome}"


def caminho_absoluto(caminho: str) -> Path:
    p = Path(caminho)
    return p if p.is_absolute() else raiz() / p


def novo_relativo(subdir: str, extensao: str) -> str:
    (raiz() / subdir).mkdir(parents=True, exist_ok=True)
    return f"{subdir}/{uuid.uuid4().hex}{extensao}"


def resolver_seguro(caminho_relativo: str) -> Path | None:
    """Resolve um caminho pedido pela URL garantindo que fica dentro do STORAGE_DIR."""
    base = raiz().resolve()
    alvo = (base / caminho_relativo).resolve()
    if not alvo.is_relative_to(base) or not alvo.is_file():
        return None
    return alvo


def url(caminho: str | None) -> str | None:
    if not caminho or Path(caminho).is_absolute():
        return None
    return f"/api/arquivos/{caminho}"
