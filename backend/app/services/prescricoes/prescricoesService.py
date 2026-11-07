from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Diagnostico, LeituraClima, Praga, Prescricao, Usuario
from app.models.enums import StatusPrescricao, TipoDiagnostico


def _hora_favoravel(leitura: LeituraClima, r: dict) -> bool:
    temperatura = leitura.temp_max if leitura.temp_max is not None else leitura.temp_med
    return (
        leitura.vento_kmh is not None
        and leitura.vento_kmh < r["vento_max_kmh"]
        and leitura.umidade_med is not None
        and leitura.umidade_med > r["umidade_min"]
        and temperatura is not None
        and temperatura < r["temp_max"]
        and not (leitura.chuva_mm or 0) > 0
    )


def encontrar_janela(db: Session, a_partir: datetime) -> tuple[datetime | None, datetime | None]:
    """Primeira sequência de horas com vento < 10 km/h, umidade > 55%, temperatura < 30 °C
    e sem chuva nas N horas seguintes (limiares em regras.toml → [janela_aplicacao])."""
    r = settings.regras["janela_aplicacao"]
    horas_chuva = timedelta(hours=r["horas_sem_chuva"])
    leituras = db.scalars(
        select(LeituraClima)
        .where(
            LeituraClima.data_hora >= a_partir,
            LeituraClima.data_hora <= a_partir + timedelta(days=r["dias_busca"]) + horas_chuva,
        )
        .order_by(LeituraClima.data_hora)
    ).all()
    chuvas = [x.data_hora for x in leituras if (x.chuva_mm or 0) > 0]
    limite = a_partir + timedelta(days=r["dias_busca"])

    inicio = fim = None
    for leitura in leituras:
        if leitura.data_hora > limite:
            break
        chove_logo = any(leitura.data_hora < c <= leitura.data_hora + horas_chuva for c in chuvas)
        if _hora_favoravel(leitura, r) and not chove_logo:
            if inicio is None:
                inicio = leitura.data_hora
            fim = leitura.data_hora + timedelta(hours=1)
        elif inicio is not None:
            break
    return inicio, fim


def sugerir(db: Session, diag: Diagnostico, a_partir: datetime | None = None) -> list[Prescricao]:
    """Diagnóstico de PRAGA → uma prescrição SUGERIDA por produto vinculado, com a dose média."""
    if diag.tipo != TipoDiagnostico.PRAGA or diag.praga_id is None:
        return []
    praga = db.get(Praga, diag.praga_id)
    inicio, fim = encontrar_janela(db, a_partir or datetime.now())
    criadas = []
    for produto in praga.produtos:
        p = Prescricao(
            diagnostico_id=diag.id,
            produto_id=produto.id,
            dose=round((produto.dose_min + produto.dose_max) / 2, 2),
            unidade=produto.unidade,
            janela_inicio=inicio,
            janela_fim=fim,
            status=StatusPrescricao.SUGERIDA,
        )
        db.add(p)
        criadas.append(p)
    db.commit()
    return criadas


TRANSICOES = {StatusPrescricao.APROVADA, StatusPrescricao.DESCARTADA, StatusPrescricao.APLICADA}


def alterar_status(db: Session, prescricao_id: int, status: StatusPrescricao, usuario: Usuario) -> Prescricao:
    p = db.get(Prescricao, prescricao_id)
    if p is None:
        raise HTTPException(404, "Prescrição não encontrada")
    if status not in TRANSICOES:
        raise HTTPException(400, "Status deve ser APROVADA, DESCARTADA ou APLICADA")
    if status == StatusPrescricao.APLICADA and p.status != StatusPrescricao.APROVADA:
        raise HTTPException(400, "Só é possível aplicar uma prescrição aprovada")
    p.status = status
    if status == StatusPrescricao.APROVADA:
        p.aprovado_por = usuario.id
    db.commit()
    db.refresh(p)
    return p
