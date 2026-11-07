"""Painéis visuais do assistente: especificações (JSON) que o frontend desenha ao lado do chat.

O modelo só escolhe *o que mostrar* (métrica, talhões, filtros). Os dados saem sempre do banco,
então um gráfico ou uma galeria nunca traz valor inventado pela IA. O frontend só desenha tipos
de painel de uma lista fixa (grafico_linhas, galeria_pragas, comparativo).
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Diagnostico
from app.models.enums import TipoDiagnostico
from app.services.dashboard import dashboardService
from app.services.diagnosticos import diagnosticosService
from app.services.talhoes import talhoesService

METRICAS = ("ndvi", "balanco_hidrico", "temperatura", "chuva")
LIMITE_FOTOS = 6


def _resumo_serie(nome: str, pontos: list[dict]) -> dict:
    valores = [p["valor"] for p in pontos]
    return {
        "nome": nome,
        "pontos": len(valores),
        "inicio": valores[0],
        "fim": valores[-1],
        "media": round(sum(valores) / len(valores), 3),
        "minimo": min(valores),
        "maximo": max(valores),
    }


def _serie_de_talhao(db: Session, talhao_id: int, metrica: str) -> dict:
    talhao = talhoesService.obter(db, talhao_id)
    campo = "ndvi_medio" if metrica == "ndvi" else "balanco_hidrico_mm"
    pontos = [
        {"data": m.data, "valor": getattr(m, campo)}
        for m in talhoesService.metricas(db, talhao_id, None, None)
        if getattr(m, campo) is not None
    ]
    return {
        "id": f"t{talhao.id}",
        "nome": talhao.nome,
        "sistema": talhao.sistema,
        "tracejado": talhao.finalidade == "SILAGEM",
        "pontos": pontos,
    }


def grafico(db: Session, metrica: str, talhao_ids: list[int] | None, titulo: str | None) -> tuple[dict, dict]:
    """Gráfico de linhas. Devolve (especificação do painel, resumo em números para o modelo comentar)."""
    if metrica not in METRICAS:
        raise ValueError(f"metrica deve ser uma de {', '.join(METRICAS)}")

    if metrica in ("ndvi", "balanco_hidrico"):
        ids = talhao_ids or [t["id"] for t in dashboardService.resumo(db)["talhoes"]]
        series = [_serie_de_talhao(db, i, metrica) for i in ids[:4]]
        series = [s for s in series if s["pontos"]]
        padrao = "NDVI por talhão" if metrica == "ndvi" else "Balanço hídrico por talhão (mm)"
        formato = (
            {"dominio": [0, 1], "casas": 2, "unidade": ""}
            if metrica == "ndvi"
            else {"dominio": ["auto", "auto"], "casas": 1, "unidade": " mm"}
        )
    else:
        campo = "temp_med" if metrica == "temperatura" else "chuva_mm"
        pontos = [
            {"data": d["data"], "valor": d[campo]}
            for d in talhoesService.clima_diario(db, None, None)
            if d[campo] is not None
        ]
        nome = "Temperatura média diária (°C)" if metrica == "temperatura" else "Chuva diária (mm)"
        cor = "#b5532a" if metrica == "temperatura" else "#3a63a8"
        series = [{"id": "clima", "nome": nome, "cor": cor, "pontos": pontos}] if pontos else []
        padrao = nome
        formato = {
            "dominio": ["auto", "auto"],
            "casas": 1,
            "unidade": " °C" if metrica == "temperatura" else " mm",
        }

    if not series:
        raise ValueError("não há dados dessa métrica para mostrar")
    spec = {"tipo": "grafico_linhas", "titulo": titulo or padrao, "series": series, **formato}
    return spec, {"series": [_resumo_serie(s["nome"], s["pontos"]) for s in series]}


def galeria_pragas(
    db: Session, talhao_id: int | None, praga: str | None, severidade: str | None, limite: int
) -> tuple[dict, dict]:
    """Fotos de armadilha com as caixas de detecção, das contagens mais altas para as mais baixas."""
    consulta = select(Diagnostico).where(
        Diagnostico.tipo == TipoDiagnostico.PRAGA, Diagnostico.imagem_id.is_not(None)
    )
    if talhao_id is not None:
        consulta = consulta.where(Diagnostico.talhao_id == talhao_id)
    if severidade:
        consulta = consulta.where(Diagnostico.severidade == severidade.upper())
    candidatos = list(db.scalars(consulta.limit(500)))
    if praga:
        candidatos = [d for d in candidatos if d.praga and praga.lower() in d.praga.nome.lower()]
    candidatos.sort(key=lambda d: (d.detalhes or {}).get("contagem") or 0, reverse=True)
    escolhidos = candidatos[: max(1, min(int(limite), LIMITE_FOTOS))]
    if not escolhidos:
        raise ValueError("nenhuma foto de armadilha encontrada com esses filtros")

    itens = []
    for d in escolhidos:
        det = diagnosticosService.detalhar(db, d.id)
        if not det["imagem"]:
            continue
        itens.append(
            {
                "diagnostico_id": d.id,
                "titulo": det["resumo"],
                "praga": det["praga_nome"],
                "talhao": det["talhao_nome"],
                "severidade": det["severidade"],
                "contagem": det["detalhes"].get("contagem"),
                "data": det["criado_em"],
                "imagem_url": det["imagem"]["url"],
                "bboxes": det["bboxes"],
            }
        )
    if not itens:
        raise ValueError("as fotos desses diagnósticos não estão disponíveis")
    spec = {"tipo": "galeria_pragas", "titulo": "Armadilhas com mais pragas", "itens": itens}
    resumo = {
        "fotos": [
            {k: i[k] for k in ("diagnostico_id", "praga", "talhao", "severidade", "contagem")} for i in itens
        ]
    }
    return spec, resumo


def comparativo(db: Session, talhao_a: int, talhao_b: int) -> tuple[dict, dict]:
    """Dois talhões lado a lado: indicadores (com o melhor destacado) e a curva de NDVI."""
    if talhao_a == talhao_b:
        raise ValueError("escolha dois talhões diferentes")
    dados = dashboardService.comparativo(db, talhao_a, talhao_b)
    a, b = dados["a"], dados["b"]

    def linha(rotulo, chave, unidade="", melhor="maior"):
        va, vb = a["indicadores"][chave], b["indicadores"][chave]
        vencedor = None
        if va is not None and vb is not None and va != vb:
            vencedor = "a" if (va > vb) == (melhor == "maior") else "b"
        return {"rotulo": rotulo, "a": va, "b": vb, "unidade": unidade, "melhor": vencedor, "sem_dados": []}

    def linha_pragas():
        # 0 pode ser "sem armadilha neste talhão": sem leituras não há comparação nem vencedor
        leituras = {"a": len(a["pragas"]), "b": len(b["pragas"])}
        va = a["indicadores"]["total_pragas"] if leituras["a"] else None
        vb = b["indicadores"]["total_pragas"] if leituras["b"] else None
        vencedor = None
        if va is not None and vb is not None and va != vb:
            vencedor = "a" if va < vb else "b"
        sem = [lado for lado, n in leituras.items() if n == 0]
        return {
            "rotulo": "Pragas capturadas",
            "a": va,
            "b": vb,
            "unidade": "",
            "melhor": vencedor,
            "sem_dados": sem,
        }

    indicadores = [
        linha("NDVI médio da safra", "ndvi_medio_periodo"),
        linha("NDVI de pico", "ndvi_maximo"),
        linha_pragas(),
    ]
    if (
        a["indicadores"]["produtividade_kg_ha"] is not None
        or b["indicadores"]["produtividade_kg_ha"] is not None
    ):
        indicadores.append(linha("Produtividade", "produtividade_kg_ha", " kg/ha"))

    series = [
        {
            "id": f"t{bl['talhao']['id']}",
            "nome": bl["talhao"]["nome"],
            "sistema": bl["talhao"]["sistema"],
            "tracejado": bl["talhao"]["finalidade"] == "SILAGEM",
            "pontos": [{"data": p["data"], "valor": p["ndvi_medio"]} for p in bl["ndvi"]],
        }
        for bl in (a, b)
    ]
    spec = {
        "tipo": "comparativo",
        "titulo": f"{a['talhao']['nome']} × {b['talhao']['nome']}",
        "talhoes": [a["talhao"], b["talhao"]],
        "indicadores": indicadores,
        "series": series,
    }
    return spec, {
        "indicadores": [{k: i[k] for k in ("rotulo", "a", "b", "melhor", "sem_dados")} for i in indicadores],
        "a": a["talhao"]["nome"],
        "b": b["talhao"]["nome"],
    }
