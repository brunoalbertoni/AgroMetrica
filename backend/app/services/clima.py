from datetime import date, datetime, time, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import LeituraClima


def balanco_hidrico(db: Session, ate: date, janela_dias: int) -> float | None:
    """Soma de (chuva − ETP) nos `janela_dias` dias terminando em `ate` (inclusive).

    Devolve None quando não há leituras de clima com ETP no período.
    """
    inicio = datetime.combine(ate - timedelta(days=janela_dias - 1), time.min)
    fim = datetime.combine(ate, time.max)
    chuva, etp, n = db.execute(
        select(
            func.sum(LeituraClima.chuva_mm),
            func.sum(LeituraClima.etp_mm),
            func.count(LeituraClima.etp_mm),
        ).where(LeituraClima.data_hora.between(inicio, fim))
    ).one()
    if not n:
        return None
    return round(float(chuva or 0) - float(etp or 0), 1)
