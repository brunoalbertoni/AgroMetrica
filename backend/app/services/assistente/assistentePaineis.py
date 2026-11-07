"""Painéis visuais do assistente: especificações (JSON) que o frontend desenha ao lado do chat.

O modelo só escolhe *o que mostrar* (métrica, talhões, filtros). Os dados saem sempre do banco,
então um gráfico ou uma galeria nunca traz valor inventado pela IA. O frontend só desenha tipos
de painel de uma lista fixa (grafico_linhas, grafico_combinado, galeria_pragas, comparativo).
"""

from datetime import date, timedelta

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


def _serie_de_talhao(
    db: Session, talhao_id: int, metrica: str, de: date | None = None, ate: date | None = None
) -> dict:
    talhao = talhoesService.obter(db, talhao_id)
    campo = "ndvi_medio" if metrica == "ndvi" else "balanco_hidrico_mm"
    pontos = [
        {"data": m.data, "valor": getattr(m, campo)}
        for m in talhoesService.metricas(db, talhao_id, de, ate)
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


# ------------------------------------------------------- gráfico analítico (NDVI x chuva + anotações)

LIMITE_ANOTACOES = 8
LIMITE_NOTAS_IA = 3
COR_CHUVA = "#3a63a8"
COR_TEMPERATURA = "#b5532a"


def _fmt(valor: float, casas: int = 2) -> str:
    return f"{valor:.{casas}f}".replace(".", ",")


def _data_iso(valor: str | None, nome: str) -> date | None:
    if not valor:
        return None
    try:
        return date.fromisoformat(str(valor)[:10])
    except ValueError:
        raise ValueError(f"{nome} deve estar no formato AAAA-MM-DD") from None


def _anotacoes_chuva(clima: list[dict], quantas: int = 3) -> list[dict]:
    ranking = sorted(
        (d for d in clima if (d["chuva_mm"] or 0) > 0), key=lambda d: d["chuva_mm"], reverse=True
    )
    return [
        {
            "data": d["data"],
            "rotulo": f"Chuva forte: {_fmt(d['chuva_mm'], 0)} mm",
            "tipo": "chuva",
            "prioridade": 1,
        }
        for d in ranking[:quantas]
    ]


def _anotacoes_ndvi(series: list[dict]) -> list[dict]:
    """Pico de NDVI e maior queda entre leituras seguidas, dos dois primeiros talhões."""
    saida = []
    for s in series[:2]:
        pontos = s["pontos"]
        if len(pontos) < 2:
            continue
        pico = max(pontos, key=lambda p: p["valor"])
        saida.append(
            {
                "data": pico["data"],
                "rotulo": f"Pico de NDVI {_fmt(pico['valor'])} - {s['nome']}",
                "tipo": "ndvi",
                "prioridade": 2,
            }
        )
        quedas = [(b["valor"] - a["valor"], b) for a, b in zip(pontos, pontos[1:], strict=False)]
        queda, ponto = min(quedas, key=lambda q: q[0])
        if queda <= -0.1:
            saida.append(
                {
                    "data": ponto["data"],
                    "rotulo": f"NDVI caiu {_fmt(-queda)} - {s['nome']}",
                    "tipo": "queda",
                    "prioridade": 2,
                }
            )
    return saida


def _nome_da_praga(diagnostico: Diagnostico) -> str:
    return diagnostico.praga.nome if diagnostico.praga else "praga"


def _anotacoes_pragas(
    db: Session, ids: list[int], nomes: dict[int, str], de: date | None, ate: date | None
) -> list[dict]:
    consulta = select(Diagnostico).where(
        Diagnostico.tipo == TipoDiagnostico.PRAGA,
        Diagnostico.severidade == "ALTA",
        Diagnostico.talhao_id.in_(ids),
    )
    achados = []
    for d in db.scalars(consulta):
        dia = d.criado_em.date()
        if (de and dia < de) or (ate and dia > ate):
            continue
        achados.append(((d.detalhes or {}).get("contagem") or 0, dia, d))
    achados.sort(key=lambda x: x[0], reverse=True)
    return [
        {
            "data": dia,
            "rotulo": f"Praga alta: {_nome_da_praga(d)} {_fmt(contagem, 0)} - {nomes[d.talhao_id]}",
            "tipo": "praga",
            "prioridade": 3,
        }
        for contagem, dia, d in achados[:2]
    ]


def _anotacoes_plantio(
    db: Session, ids: list[int], nomes: dict[int, str], de: date | None, ate: date | None
) -> list[dict]:
    saida = []
    for i in ids[:2]:
        for op in talhoesService.operacoes(db, i):
            fora = (de and op.data_inicio < de) or (ate and op.data_inicio > ate)
            if op.operacao == "Plantio" and not fora:
                saida.append(
                    {
                        "data": op.data_inicio,
                        "rotulo": f"Plantio - {nomes[i]}",
                        "tipo": "manejo",
                        "prioridade": 4,
                    }
                )
    return saida


def _notas_do_modelo(notas: list[str] | None, de: date | None, ate: date | None) -> tuple[list[dict], int]:
    """Notas livres do modelo ('AAAA-MM-DD: texto'); data inválida ou fora do período é descartada."""
    validas, ignoradas = [], 0
    for nota in (notas or [])[:LIMITE_NOTAS_IA]:
        data_txt, _, texto = str(nota).partition(":")
        try:
            dia = date.fromisoformat(data_txt.strip()[:10])
        except ValueError:
            ignoradas += 1
            continue
        texto = texto.strip()[:80]
        if not texto or (de and dia < de) or (ate and dia > ate):
            ignoradas += 1
            continue
        validas.append({"data": dia, "rotulo": texto, "tipo": "ia", "prioridade": 0})
    return validas, ignoradas


def _ndvi_em_torno(pontos: list[dict], dia: date, janela_dias: int = 21) -> dict:
    antes = [p for p in pontos if p["data"] <= dia]
    depois = [p for p in pontos if dia < p["data"] <= dia + timedelta(days=janela_dias)]
    return {
        "ndvi_antes": antes[-1]["valor"] if antes else None,
        "ndvi_depois": depois[0]["valor"] if depois else None,
    }


def grafico_analitico(
    db: Session,
    talhao_ids: list[int] | None,
    metrica: str,
    complemento: str | None,
    de: str | None,
    ate: str | None,
    anotar: bool,
    notas: list[str] | None,
) -> tuple[dict, dict]:
    """Linhas por talhão (NDVI ou balanço hídrico) + clima da fazenda (chuva em barras ou temperatura),
    com anotações calculadas dos dados e o resumo em números para o modelo fazer a análise."""
    if metrica not in ("ndvi", "balanco_hidrico"):
        raise ValueError("metrica deve ser 'ndvi' ou 'balanco_hidrico'")
    if complemento not in (None, "chuva", "temperatura"):
        raise ValueError("complemento deve ser 'chuva', 'temperatura' ou vazio")
    inicio, fim = _data_iso(de, "de"), _data_iso(ate, "ate")

    ids = talhao_ids or [t["id"] for t in dashboardService.resumo(db)["talhoes"]]
    series = [_serie_de_talhao(db, i, metrica, inicio, fim) for i in ids[:4]]
    series = [s for s in series if s["pontos"]]
    if not series:
        raise ValueError("não há dados desse talhão no período")
    nomes = {int(s["id"][1:]): s["nome"] for s in series}

    clima = []
    if complemento:
        campo = "chuva_mm" if complemento == "chuva" else "temp_med"
        clima = [d for d in talhoesService.clima_diario(db, inicio, fim) if d[campo] is not None]
        if not clima:
            raise ValueError("não há dados de clima no período")
        if not inicio:  # sem período informado: o do clima, para as barras e as linhas se encontrarem
            inicio, fim = clima[0]["data"], clima[-1]["data"]
            for s in series:
                s["pontos"] = [p for p in s["pontos"] if inicio <= p["data"] <= fim] or s["pontos"]

    anotacoes = []
    if anotar:
        if complemento == "chuva":
            anotacoes += _anotacoes_chuva(clima)
        if metrica == "ndvi":
            anotacoes += _anotacoes_ndvi(series)
        anotacoes += _anotacoes_pragas(db, list(nomes), nomes, inicio, fim)
        anotacoes += _anotacoes_plantio(db, list(nomes), nomes, inicio, fim)
    extras, ignoradas = _notas_do_modelo(notas, inicio, fim)
    anotacoes = sorted(anotacoes, key=lambda a: a["prioridade"])[: LIMITE_ANOTACOES - len(extras)] + extras
    anotacoes.sort(key=lambda a: (a["data"], a["prioridade"]))
    for n, a in enumerate(anotacoes, start=1):
        a["id"] = n
        a["data"] = a["data"].isoformat() if isinstance(a["data"], date) else a["data"]
        a.pop("prioridade", None)

    esquerda = (
        {"rotulo": "NDVI", "dominio": [0, 1], "casas": 2, "unidade": ""}
        if metrica == "ndvi"
        else {"rotulo": "Balanço hídrico (mm)", "dominio": ["auto", "auto"], "casas": 1, "unidade": " mm"}
    )
    eixos = {"esq": esquerda}
    todas = [{**s, "tipo": "linha", "eixo": "esq"} for s in series]
    if complemento == "chuva":
        eixos["dir"] = {"rotulo": "Chuva (mm)", "casas": 0, "unidade": " mm"}
        todas.append(
            {
                "id": "clima",
                "nome": "Chuva diária (mm)",
                "tipo": "barra",
                "eixo": "dir",
                "cor": COR_CHUVA,
                "pontos": [{"data": d["data"], "valor": d["chuva_mm"]} for d in clima],
            }
        )
    elif complemento == "temperatura":
        eixos["dir"] = {"rotulo": "Temperatura (°C)", "casas": 1, "unidade": " °C"}
        todas.append(
            {
                "id": "clima",
                "nome": "Temperatura média (°C)",
                "tipo": "linha",
                "eixo": "dir",
                "cor": COR_TEMPERATURA,
                "pontos": [{"data": d["data"], "valor": d["temp_med"]} for d in clima],
            }
        )

    rotulo_metrica = "NDVI" if metrica == "ndvi" else "Balanço hídrico"
    juntos = {"chuva": " × chuva", "temperatura": " × temperatura"}.get(complemento, "")
    spec = {
        "tipo": "grafico_combinado",
        "titulo": f"{rotulo_metrica}{juntos} - {', '.join(nomes.values())}",
        "eixos": eixos,
        "series": todas,
        "anotacoes": anotacoes,
    }

    resumo: dict = {
        "periodo": [inicio.isoformat() if inicio else None, fim.isoformat() if fim else None],
        "series": [_resumo_serie(s["nome"], s["pontos"]) for s in series],
        "anotacoes_no_grafico": [{k: a[k] for k in ("data", "rotulo", "tipo")} for a in anotacoes],
        "notas_do_modelo_ignoradas": ignoradas,
    }
    if complemento == "chuva":
        chuvas = [d["chuva_mm"] for d in clima]
        resumo["chuva"] = {
            "total_mm": round(sum(chuvas), 1),
            "dias_com_chuva": sum(1 for c in chuvas if c > 0),
            "obs": "chuva medida por UMA estação para a fazenda toda: é igual para todos os talhões",
        }
        if metrica == "ndvi":
            resumo["ndvi_antes_e_depois_das_chuvas_fortes"] = [
                {
                    "data": a["data"],
                    "chuva": a["rotulo"],
                    "talhoes": [
                        {"nome": s["nome"], **_ndvi_em_torno(s["pontos"], date.fromisoformat(a["data"]))}
                        for s in series
                    ],
                }
                for a in anotacoes
                if a["tipo"] == "chuva"
            ]
    return spec, resumo
