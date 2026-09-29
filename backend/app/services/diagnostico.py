"""Motor de diagnóstico v1, baseado em regras.

Os limiares de NDVI, balanço hídrico e solo vêm de app/core/regras.toml (settings.regras);
os de praga vêm do cadastro da praga.
"""

from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models import Diagnostico, LeituraClima, LeituraSolo, MetricaTalhao, Praga, Talhao
from app.models.enums import Severidade, TipoDiagnostico
from app.services import alertas, prescricao
from app.services.clima import balanco_hidrico

_ORDEM = {None: 0, Severidade.BAIXA: 1, Severidade.MEDIA: 2, Severidade.ALTA: 3}


def classificar_praga(contagem: float, praga: Praga) -> Severidade | None:
    if contagem >= praga.limiar_dano:
        return Severidade.ALTA
    if contagem >= praga.limiar_controle:
        return Severidade.MEDIA
    if contagem >= praga.limiar_alerta:
        return Severidade.BAIXA
    return None


def avaliar_ndvi(anterior: float | None, atual: float | None, regras: dict) -> Severidade | None:
    if anterior is None or atual is None or anterior <= 0:
        return None
    queda = (anterior - atual) / anterior
    if queda > regras["ndvi"]["queda_alta"]:
        return Severidade.ALTA
    if queda > regras["ndvi"]["queda_media"]:
        return Severidade.MEDIA
    return None


def avaliar_hidrico(balanco_mm: float | None, regras: dict) -> Severidade | None:
    if balanco_mm is not None and balanco_mm < regras["hidrico"]["limite_mm"]:
        return Severidade.MEDIA
    return None


_ROTULOS_SOLO = {
    "ph": ("pH", "ph_min"),
    "v_pct": ("V%", "v_pct_min"),
    "p": ("P", "p_min"),
    "k": ("K", "k_min"),
}


def avaliar_solo(leitura: LeituraSolo, regras: dict) -> tuple[Severidade | None, list[str]]:
    """pH, V%, P ou K abaixo do mínimo → BAIXA; abaixo de fator_media × mínimo → MEDIA."""
    r = regras["solo"]
    severidade, problemas = None, []
    for campo, (rotulo, chave) in _ROTULOS_SOLO.items():
        valor, minimo = getattr(leitura, campo), r[chave]
        if valor is None or valor >= minimo:
            continue
        problemas.append(f"{rotulo} {valor:g} abaixo de {minimo:g}")
        nivel = Severidade.MEDIA if valor < minimo * r["fator_media"] else Severidade.BAIXA
        if _ORDEM[nivel] > _ORDEM[severidade]:
            severidade = nivel
    return severidade, problemas


def _ja_existe(db: Session, talhao_id: int, tipo: TipoDiagnostico, chave: str) -> bool:
    existentes = db.scalars(
        select(Diagnostico.detalhes).where(Diagnostico.talhao_id == talhao_id, Diagnostico.tipo == tipo)
    )
    return any((d or {}).get("chave") == chave for d in existentes)


def _criar(
    db: Session,
    talhao_id: int,
    tipo: TipoDiagnostico,
    severidade: Severidade,
    detalhes: dict,
    quando: datetime | None = None,
    **extra,
) -> Diagnostico:
    diag = Diagnostico(talhao_id=talhao_id, tipo=tipo, severidade=severidade, detalhes=detalhes, **extra)
    if quando is not None:
        diag.criado_em = quando
    db.add(diag)
    db.commit()
    db.refresh(diag)
    alertas.gerar_para(db, diag)
    return diag


def registrar_armadilha(
    db: Session,
    talhao_id: int,
    praga_id: int,
    contagem: float,
    data: datetime,
    imagem_id: int | None = None,
    bboxes: list[dict] | None = None,
    confianca: float | None = None,
) -> Diagnostico | None:
    """Leitura de armadilha → diagnóstico de PRAGA (se atingir o limiar de alerta) + prescrição sugerida."""
    praga = db.get(Praga, praga_id)
    if praga is None:
        raise HTTPException(404, "Praga não encontrada")
    if db.get(Talhao, talhao_id) is None:
        raise HTTPException(404, "Talhão não encontrado")
    severidade = classificar_praga(contagem, praga)
    if severidade is None:
        return None
    detalhes = {
        "chave": f"PRAGA:{praga_id}:{imagem_id or ''}:{data.isoformat()}",
        "contagem": contagem,
        "data": data.isoformat(),
        "limiares": {
            "alerta": praga.limiar_alerta,
            "controle": praga.limiar_controle,
            "dano": praga.limiar_dano,
        },
        "bboxes": bboxes or [],
    }
    diag = _criar(
        db,
        talhao_id,
        TipoDiagnostico.PRAGA,
        severidade,
        detalhes,
        quando=data,
        praga_id=praga_id,
        imagem_id=imagem_id,
        confianca=confianca if confianca is not None else 1.0,
    )
    prescricao.sugerir(db, diag, a_partir=data)
    return diag


def _rodar_ndvi(db: Session, talhao_id: int, regras: dict) -> Diagnostico | None:
    ultimas = db.scalars(
        select(MetricaTalhao)
        .where(MetricaTalhao.talhao_id == talhao_id, MetricaTalhao.ndvi_medio.is_not(None))
        .order_by(MetricaTalhao.data.desc())
        .limit(2)
    ).all()
    if len(ultimas) < 2:
        return None
    atual, anterior = ultimas
    severidade = avaliar_ndvi(anterior.ndvi_medio, atual.ndvi_medio, regras)
    chave = f"VIGOR:{atual.data.isoformat()}"
    if severidade is None or _ja_existe(db, talhao_id, TipoDiagnostico.VIGOR, chave):
        return None
    queda = (anterior.ndvi_medio - atual.ndvi_medio) / anterior.ndvi_medio
    detalhes = {
        "chave": chave,
        "data": atual.data.isoformat(),
        "data_anterior": anterior.data.isoformat(),
        "ndvi_anterior": anterior.ndvi_medio,
        "ndvi_atual": atual.ndvi_medio,
        "queda_pct": round(queda * 100, 1),
    }
    return _criar(
        db,
        talhao_id,
        TipoDiagnostico.VIGOR,
        severidade,
        detalhes,
        quando=datetime.combine(atual.data, datetime.min.time()),
        confianca=1.0,
    )


def _rodar_hidrico(db: Session, talhao_id: int, regras: dict) -> Diagnostico | None:
    ultima = db.scalar(select(func.max(LeituraClima.data_hora)))
    if ultima is None:
        return None
    referencia = ultima.date() if isinstance(ultima, datetime) else datetime.fromisoformat(str(ultima)).date()
    janela = regras["hidrico"]["janela_dias"]
    balanco = balanco_hidrico(db, referencia, janela)
    severidade = avaliar_hidrico(balanco, regras)
    chave = f"HIDRICO:{referencia.isoformat()}"
    if severidade is None or _ja_existe(db, talhao_id, TipoDiagnostico.HIDRICO, chave):
        return None
    detalhes = {
        "chave": chave,
        "data": referencia.isoformat(),
        "janela_dias": janela,
        "balanco_mm": balanco,
        "limite_mm": regras["hidrico"]["limite_mm"],
    }
    return _criar(
        db,
        talhao_id,
        TipoDiagnostico.HIDRICO,
        severidade,
        detalhes,
        quando=datetime.combine(referencia, datetime.min.time()),
        confianca=1.0,
    )


def _rodar_solo(db: Session, talhao_id: int, regras: dict) -> Diagnostico | None:
    ultima_coleta = db.scalar(
        select(func.max(LeituraSolo.data_coleta)).where(LeituraSolo.talhao_id == talhao_id)
    )
    if ultima_coleta is None:
        return None
    leituras = db.scalars(
        select(LeituraSolo).where(
            LeituraSolo.talhao_id == talhao_id, LeituraSolo.data_coleta == ultima_coleta
        )
    ).all()
    pior, pontos = None, []
    for leitura in leituras:
        severidade, problemas = avaliar_solo(leitura, regras)
        if problemas:
            pontos.append(
                {
                    "ponto": leitura.ponto,
                    "severidade": severidade,
                    "problemas": problemas,
                    "lat": leitura.lat,
                    "lon": leitura.lon,
                }
            )
        if _ORDEM[severidade] > _ORDEM[pior]:
            pior = severidade
    chave = f"NUTRICIONAL:{ultima_coleta.isoformat()}"
    if pior is None or _ja_existe(db, talhao_id, TipoDiagnostico.NUTRICIONAL, chave):
        return None
    detalhes = {
        "chave": chave,
        "data": ultima_coleta.isoformat(),
        "pontos": pontos,
        "pontos_avaliados": len(leituras),
    }
    return _criar(
        db,
        talhao_id,
        TipoDiagnostico.NUTRICIONAL,
        pior,
        detalhes,
        quando=datetime.combine(ultima_coleta, datetime.min.time()),
        confianca=1.0,
    )


def listar(
    db: Session,
    talhao_id: int | None = None,
    severidade: Severidade | None = None,
    tipo: TipoDiagnostico | None = None,
    limite: int = 500,
) -> list[dict]:
    consulta = select(Diagnostico)
    if talhao_id is not None:
        consulta = consulta.where(Diagnostico.talhao_id == talhao_id)
    if severidade is not None:
        consulta = consulta.where(Diagnostico.severidade == severidade)
    if tipo is not None:
        consulta = consulta.where(Diagnostico.tipo == tipo)
    diags = db.scalars(consulta.order_by(Diagnostico.criado_em.desc(), Diagnostico.id.desc()).limit(limite))
    return [representar(db, d) for d in diags]


def representar(db: Session, diag: Diagnostico) -> dict:
    return {
        "id": diag.id,
        "talhao_id": diag.talhao_id,
        "talhao_nome": diag.talhao.nome if diag.talhao else None,
        "imagem_id": diag.imagem_id,
        "praga_id": diag.praga_id,
        "praga_nome": diag.praga.nome if diag.praga else None,
        "tipo": diag.tipo,
        "severidade": diag.severidade,
        "confianca": diag.confianca,
        "criado_em": diag.criado_em,
        "resumo": alertas.mensagem(db, diag),
    }


def detalhar(db: Session, diagnostico_id: int) -> dict:
    from app.services.imagem import representar as representar_imagem

    diag = db.get(Diagnostico, diagnostico_id)
    if diag is None:
        raise HTTPException(404, "Diagnóstico não encontrado")
    detalhes = diag.detalhes or {}
    return {
        **representar(db, diag),
        "detalhes": detalhes,
        "bboxes": detalhes.get("bboxes", []),
        "imagem": representar_imagem(diag.imagem) if diag.imagem else None,
        "prescricoes": diag.prescricoes,
    }


def rodar(db: Session, talhao_id: int) -> list[Diagnostico]:
    """Executa as regras de vigor, hídrico e nutricional. Não duplica diagnósticos já gerados."""
    if db.get(Talhao, talhao_id) is None:
        raise HTTPException(404, "Talhão não encontrado")
    regras = settings.regras
    criados = [f(db, talhao_id, regras) for f in (_rodar_ndvi, _rodar_hidrico, _rodar_solo)]
    return [d for d in criados if d is not None]
