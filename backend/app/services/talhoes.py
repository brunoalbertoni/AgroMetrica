from datetime import date

from fastapi import HTTPException
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import LeituraClima, LeituraSolo, MetricaTalhao, Talhao

CAMPOS_ORDENACAO = {"id", "nome", "area_ha", "cultura", "sistema", "finalidade"}


def obter(db: Session, talhao_id: int) -> Talhao:
    talhao = db.get(Talhao, talhao_id)
    if talhao is None:
        raise HTTPException(404, "Talhão não encontrado")
    return talhao


def ultima_metrica(db: Session, talhao_id: int) -> MetricaTalhao | None:
    return db.scalar(
        select(MetricaTalhao)
        .where(MetricaTalhao.talhao_id == talhao_id)
        .order_by(MetricaTalhao.data.desc())
        .limit(1)
    )


def _subquery_ultimo_balanco():
    """Último balanço hídrico registrado de cada talhão."""
    ultima_data = (
        select(MetricaTalhao.talhao_id, func.max(MetricaTalhao.data).label("data"))
        .where(MetricaTalhao.balanco_hidrico_mm.is_not(None))
        .group_by(MetricaTalhao.talhao_id)
        .subquery()
    )
    return (
        select(MetricaTalhao.talhao_id, MetricaTalhao.balanco_hidrico_mm)
        .join(
            ultima_data,
            (ultima_data.c.talhao_id == MetricaTalhao.talhao_id) & (ultima_data.c.data == MetricaTalhao.data),
        )
        .subquery()
    )


def listar(
    db: Session,
    page: int,
    size: int,
    sort: str | None,
    busca: str | None,
    deficit_min: float | None,
    sistema: str | None,
) -> dict:
    consulta = select(Talhao)
    if busca:
        termo = f"%{busca.strip()}%"
        consulta = consulta.where(or_(Talhao.nome.ilike(termo), Talhao.cultura.ilike(termo)))
    if sistema:
        consulta = consulta.where(Talhao.sistema == sistema)
    if deficit_min is not None:
        balanco = _subquery_ultimo_balanco()
        consulta = consulta.join(balanco, balanco.c.talhao_id == Talhao.id).where(
            balanco.c.balanco_hidrico_mm <= -abs(deficit_min)
        )

    total = db.scalar(select(func.count()).select_from(consulta.subquery()))

    campo = (sort or "id").lstrip("-")
    if campo not in CAMPOS_ORDENACAO:
        raise HTTPException(400, f"Ordenação inválida: {sort}")
    coluna = getattr(Talhao, campo)
    consulta = consulta.order_by(coluna.desc() if sort and sort.startswith("-") else coluna.asc(), Talhao.id)

    itens = db.scalars(consulta.offset((page - 1) * size).limit(size)).all()
    for t in itens:
        t.ultima_metrica = ultima_metrica(db, t.id)
    return {"items": itens, "total": total, "page": page, "size": size}


def detalhe(db: Session, talhao_id: int) -> Talhao:
    talhao = obter(db, talhao_id)
    talhao.ultima_metrica = ultima_metrica(db, talhao_id)
    return talhao


def metricas(db: Session, talhao_id: int, de: date | None, ate: date | None) -> list[MetricaTalhao]:
    obter(db, talhao_id)
    consulta = select(MetricaTalhao).where(MetricaTalhao.talhao_id == talhao_id)
    if de:
        consulta = consulta.where(MetricaTalhao.data >= de)
    if ate:
        consulta = consulta.where(MetricaTalhao.data <= ate)
    return list(db.scalars(consulta.order_by(MetricaTalhao.data)))


def classificar_solo(leitura: LeituraSolo) -> dict[str, str]:
    """BAIXO/ADEQUADO para os indicadores que o motor de diagnóstico usa (limiares em regras.toml)."""
    r = settings.regras["solo"]
    limites = {"ph": r["ph_min"], "v_pct": r["v_pct_min"], "p": r["p_min"], "k": r["k_min"]}
    classes = {}
    for campo, minimo in limites.items():
        valor = getattr(leitura, campo)
        if valor is not None:
            classes[campo] = "BAIXO" if valor < minimo else "ADEQUADO"
    return classes


def solo(db: Session, talhao_id: int) -> list[LeituraSolo]:
    obter(db, talhao_id)
    leituras = list(
        db.scalars(
            select(LeituraSolo)
            .where(LeituraSolo.talhao_id == talhao_id)
            .order_by(LeituraSolo.data_coleta.desc(), LeituraSolo.ponto)
        )
    )
    for leitura in leituras:
        leitura.classificacao = classificar_solo(leitura)
    return leituras


def clima_diario(db: Session, de: date | None, ate: date | None) -> list[dict]:
    dia = func.date(LeituraClima.data_hora).label("dia")
    consulta = (
        select(
            dia,
            func.min(LeituraClima.temp_min),
            func.avg(LeituraClima.temp_med),
            func.max(LeituraClima.temp_max),
            func.sum(LeituraClima.chuva_mm),
            func.avg(LeituraClima.umidade_med),
            func.avg(LeituraClima.vento_kmh),
            func.sum(LeituraClima.radiacao),
            func.sum(LeituraClima.etp_mm),
        )
        .group_by(dia)
        .order_by(dia)
    )
    if de:
        consulta = consulta.where(LeituraClima.data_hora >= de)
    if ate:
        consulta = consulta.where(func.date(LeituraClima.data_hora) <= ate)
    chaves = [
        "temp_min",
        "temp_med",
        "temp_max",
        "chuva_mm",
        "umidade_med",
        "vento_kmh",
        "radiacao",
        "etp_mm",
    ]
    saida = []
    for linha in db.execute(consulta):
        d = linha[0] if isinstance(linha[0], date) else date.fromisoformat(str(linha[0]))
        valores = {
            k: (round(float(v), 2) if v is not None else None) for k, v in zip(chaves, linha[1:], strict=True)
        }
        saida.append({"data": d, **valores})
    return saida
