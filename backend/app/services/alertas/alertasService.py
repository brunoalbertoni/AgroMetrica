from fastapi import HTTPException
from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.models import Alerta, Diagnostico, Praga, Talhao
from app.models.enums import Severidade, TipoDiagnostico

GERAM_ALERTA = {Severidade.MEDIA, Severidade.ALTA}


def _num(valor, casas: int = 1) -> str:
    """Número no padrão brasileiro (vírgula decimal, sinal de menos tipográfico)."""
    if not isinstance(valor, (int, float)):
        return "?"
    texto = f"{abs(valor):,.{casas}f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"−{texto}" if valor < 0 else texto


def mensagem(db: Session, diag: Diagnostico) -> str:
    talhao = db.get(Talhao, diag.talhao_id)
    d = diag.detalhes or {}
    nome = talhao.nome if talhao else f"talhão {diag.talhao_id}"
    if diag.tipo == TipoDiagnostico.PRAGA:
        praga = db.get(Praga, diag.praga_id) if diag.praga_id else None
        nivel = {"ALTA": "nível de dano", "MEDIA": "nível de controle"}.get(
            diag.severidade, "nível de alerta"
        )
        contagem = _num(d.get("contagem"), 0)
        return f"{praga.nome if praga else 'Praga'}: {nivel} ({contagem} na armadilha) em {nome}"
    if diag.tipo == TipoDiagnostico.VIGOR:
        return f"Queda de {_num(d.get('queda_pct'))}% no NDVI em {nome}"
    if diag.tipo == TipoDiagnostico.HIDRICO:
        balanco = _num(d.get("balanco_mm"))
        return f"Déficit hídrico de {balanco} mm em {d.get('janela_dias', 7)} dias em {nome}"
    return f"Problema nutricional no solo de {nome}"


def gerar_para(db: Session, diag: Diagnostico) -> Alerta | None:
    """MEDIA (amarelo) e ALTA (vermelho) geram alerta; BAIXA não."""
    if diag.severidade not in GERAM_ALERTA:
        return None
    alerta = Alerta(
        talhao_id=diag.talhao_id,
        diagnostico_id=diag.id,
        severidade=diag.severidade,
        mensagem=mensagem(db, diag)[:300],
        lido=False,
    )
    db.add(alerta)
    db.commit()
    return alerta


def listar(db: Session, lido: bool | None) -> list[Alerta]:
    consulta = select(Alerta)
    if lido is not None:
        consulta = consulta.where(Alerta.lido == lido)
    alta_primeiro = case((Alerta.severidade == Severidade.ALTA, 0), else_=1)
    return list(db.scalars(consulta.order_by(alta_primeiro, Alerta.criado_em.desc(), Alerta.id.desc())))


def marcar_lido(db: Session, alerta_id: int) -> Alerta:
    alerta = db.get(Alerta, alerta_id)
    if alerta is None:
        raise HTTPException(404, "Alerta não encontrado")
    alerta.lido = True
    db.commit()
    db.refresh(alerta)
    return alerta
