from collections import defaultdict
from datetime import datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Diagnostico, MetricaTalhao, Talhao
from app.models.enums import Severidade, TipoDiagnostico
from app.services import alertas as alertas_svc
from app.services import talhoes as talhoes_svc

_PESO = {Severidade.MEDIA: 1, Severidade.ALTA: 2}


def _talhao_basico(t: Talhao) -> dict:
    return {
        "id": t.id,
        "nome": t.nome,
        "sistema": t.sistema,
        "finalidade": t.finalidade,
        "cultura": t.cultura,
        "area_ha": float(t.area_ha),
    }


def _series_ndvi(db: Session) -> dict[int, list[dict]]:
    series: dict[int, list[dict]] = defaultdict(list)
    for m in db.scalars(
        select(MetricaTalhao).where(MetricaTalhao.ndvi_medio.is_not(None)).order_by(MetricaTalhao.data)
    ):
        series[m.talhao_id].append({"data": m.data, "ndvi": m.ndvi_medio})
    return series


def resumo(db: Session) -> dict:
    talhoes = list(db.scalars(select(Talhao).order_by(Talhao.id)))
    abertos = alertas_svc.listar(db, lido=False)
    series = _series_ndvi(db)

    severidade: dict[int, Severidade] = {}
    for a in abertos:
        atual = severidade.get(a.talhao_id)
        if atual is None or _PESO[a.severidade] > _PESO[atual]:
            severidade[a.talhao_id] = a.severidade

    ultimos = [s[-1]["ndvi"] for s in series.values() if s]
    return {
        "cards": {
            "talhoes": len(talhoes),
            "area_total_ha": round(sum(float(t.area_ha) for t in talhoes), 2),
            "alertas_abertos": len(abertos),
            "alertas_altos": sum(1 for a in abertos if a.severidade == Severidade.ALTA),
            "diagnosticos": db.scalar(select(func.count()).select_from(Diagnostico)),
            "ndvi_medio_atual": round(sum(ultimos) / len(ultimos), 3) if ultimos else None,
        },
        "ndvi_por_talhao": [
            {"talhao_id": t.id, "nome": t.nome, "sistema": t.sistema, "serie": series.get(t.id, [])}
            for t in talhoes
        ],
        "talhoes": [
            {
                **_talhao_basico(t),
                "geometria": t.geometria,
                "severidade": severidade.get(t.id),
                "ultimo_ndvi": series[t.id][-1]["ndvi"] if series.get(t.id) else None,
            }
            for t in talhoes
        ],
    }


def _bloco(db: Session, talhao: Talhao) -> dict:
    metricas = list(
        db.scalars(
            select(MetricaTalhao).where(MetricaTalhao.talhao_id == talhao.id).order_by(MetricaTalhao.data)
        )
    )
    ndvi = [
        {
            "data": m.data,
            "ndvi_medio": m.ndvi_medio,
            "ndvi_min": m.ndvi_min,
            "ndvi_max": m.ndvi_max,
            "balanco_hidrico_mm": m.balanco_hidrico_mm,
        }
        for m in metricas
        if m.ndvi_medio is not None
    ]
    produtividade = [
        {"data": m.data, "produtividade_kg_ha": m.produtividade_kg_ha}
        for m in metricas
        if m.produtividade_kg_ha is not None
    ]
    diags = list(
        db.scalars(
            select(Diagnostico)
            .where(Diagnostico.talhao_id == talhao.id, Diagnostico.tipo == TipoDiagnostico.PRAGA)
            .order_by(Diagnostico.criado_em)
        )
    )
    pragas = [
        {
            "data": d.criado_em,
            "contagem": (d.detalhes or {}).get("contagem"),
            "praga": d.praga.nome if d.praga else None,
            "severidade": d.severidade,
            "diagnostico_id": d.id,
        }
        for d in diags
    ]
    valores_ndvi = [p["ndvi_medio"] for p in ndvi]
    return {
        "talhao": _talhao_basico(talhao),
        "ndvi": ndvi,
        "produtividade": produtividade,
        "pragas": pragas,
        "indicadores": {
            "ndvi_medio_periodo": round(sum(valores_ndvi) / len(valores_ndvi), 3) if valores_ndvi else None,
            "ndvi_maximo": max(valores_ndvi) if valores_ndvi else None,
            "produtividade_kg_ha": produtividade[-1]["produtividade_kg_ha"] if produtividade else None,
            "total_pragas": sum(p["contagem"] or 0 for p in pragas),
        },
    }


def comparativo(db: Session, a_id: int, b_id: int) -> dict:
    a, b = talhoes_svc.obter(db, a_id), talhoes_svc.obter(db, b_id)
    bloco_a, bloco_b = _bloco(db, a), _bloco(db, b)

    datas = [p["data"] for bl in (bloco_a, bloco_b) for p in bl["ndvi"] + bl["produtividade"]]
    datas += [
        p["data"].date() if isinstance(p["data"], datetime) else p["data"]
        for bl in (bloco_a, bloco_b)
        for p in bl["pragas"]
    ]
    clima = talhoes_svc.clima_diario(db, min(datas), max(datas)) if datas else []

    eventos = []
    for d in db.scalars(
        select(Diagnostico).where(Diagnostico.talhao_id.in_([a_id, b_id])).order_by(Diagnostico.criado_em)
    ):
        eventos.append(
            {
                "diagnostico_id": d.id,
                "talhao_id": d.talhao_id,
                "data": d.criado_em,
                "tipo": d.tipo,
                "severidade": d.severidade,
                "resumo": alertas_svc.mensagem(db, d),
            }
        )
    return {"a": bloco_a, "b": bloco_b, "clima": clima, "eventos": eventos}
