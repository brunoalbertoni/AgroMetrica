"""Tools de consulta (somente leitura) que o agente chama quando a pergunta pede dados.

Cada tool é uma função simples com docstring: o SDK do Gemini monta a declaração a partir da
assinatura e do texto. Retornam sempre dados JSON; erros viram {"erro": "..."} para o modelo
explicar ao usuário em vez de derrubar a conversa.
"""

from collections.abc import Callable
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from functools import wraps

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models.enums import Severidade
from app.services.alertas import alertasService as alertas
from app.services.assistente import assistentePaineis as paineis_svc
from app.services.dashboard import dashboardService as dashboard
from app.services.diagnosticos import diagnosticosService as diagnostico
from app.services.pragas import pragasService
from app.services.produtos import produtosService
from app.services.talhoes import talhoesService as talhoes

LIMITE_MAX = 50
LIMITE_PAINEIS = 2  # painéis por resposta: cada um é uma chamada a mais ao Gemini


def _limpar(valor):
    """Converte datas, enums e decimais em tipos JSON."""
    if isinstance(valor, dict):
        return {k: _limpar(v) for k, v in valor.items()}
    if isinstance(valor, (list, tuple)):
        return [_limpar(v) for v in valor]
    if isinstance(valor, (datetime, date)):
        return valor.isoformat()
    if isinstance(valor, Enum):
        return valor.value
    if isinstance(valor, Decimal):
        return float(valor)
    return valor


def _linha(obj, *, excluir: tuple[str, ...] = ()) -> dict:
    return _limpar({c.name: getattr(obj, c.name) for c in obj.__table__.columns if c.name not in excluir})


def _limite(valor: int) -> int:
    return max(1, min(int(valor), LIMITE_MAX))


def _segura(funcao: Callable) -> Callable:
    @wraps(funcao)
    def interna(*args, **kwargs):
        try:
            return _limpar(funcao(*args, **kwargs))
        except HTTPException as erro:
            return {"erro": str(erro.detail)}
        except (ValueError, KeyError) as erro:
            return {"erro": f"Parâmetro inválido: {erro}"}

    return interna


def criar_tools(db: Session, paineis: list | None = None) -> list[Callable]:
    """Tools ligadas à sessão do banco desta requisição.

    As tools `mostrar_*` não devolvem o gráfico ao modelo: elas acrescentam a especificação do painel
    em `paineis`, que o controller entrega ao frontend junto com o texto da resposta.
    """
    paineis = [] if paineis is None else paineis

    @_segura
    def resumo_geral() -> dict:
        """Visão geral do sistema: totais (talhões, área, alertas abertos, diagnósticos, NDVI médio
        atual) e a lista de talhões com id, nome, sistema (AGRO_4_0 ou CONVENCIONAL), finalidade,
        área, severidade do pior alerta e último NDVI. Use primeiro para descobrir os ids."""
        r = dashboard.resumo(db)
        return {
            "cards": r["cards"],
            "talhoes": [{k: v for k, v in t.items() if k != "geometria"} for t in r["talhoes"]],
        }

    @_segura
    def consultar_talhao(talhao_id: int) -> dict:
        """Detalhes de um talhão: dados cadastrais, operações de manejo (calagem, gessagem, adubação,
        plantio, com doses e datas), última métrica (NDVI, balanço hídrico, produtividade) e as
        leituras de solo mais recentes com a classificação de cada nutriente."""
        t = talhoes.detalhe(db, talhao_id)
        ultima = talhoes.ultima_metrica(db, talhao_id)
        return {
            "talhao": _linha(t, excluir=("geometria",)),
            "operacoes": [_linha(o) for o in talhoes.operacoes(db, talhao_id)],
            "ultima_metrica": _linha(ultima) if ultima else None,
            "solo_recente": [
                {**_linha(s), "classificacao": s.classificacao} for s in talhoes.solo(db, talhao_id)[:6]
            ],
        }

    @_segura
    def serie_ndvi(talhao_id: int, limite: int = 20) -> dict:
        """Série temporal de NDVI e balanço hídrico de um talhão, da data mais recente para a mais
        antiga. `limite` é quantos pontos devolver (máximo 50)."""
        pontos = talhoes.metricas(db, talhao_id, None, None)
        recentes = pontos[-_limite(limite) :][::-1]
        return {
            "talhao_id": talhao_id,
            "total_de_pontos": len(pontos),
            "pontos": [_linha(p, excluir=("id", "talhao_id")) for p in recentes],
        }

    @_segura
    def clima_diario(dias: int = 14) -> dict:
        """Clima diário da estação (temperatura, chuva, umidade, radiação, vento, ETP) dos últimos
        `dias` dias com dados (máximo 50)."""
        serie = talhoes.clima_diario(db, None, None)
        return {"dias": serie[-_limite(dias) :]}

    @_segura
    def listar_alertas(apenas_abertos: bool = True, limite: int = 20) -> dict:
        """Alertas do sistema, os de severidade alta primeiro. Por padrão só os não lidos."""
        itens = alertas.listar(db, lido=False if apenas_abertos else None)[: _limite(limite)]
        return {
            "alertas": [
                {
                    "id": a.id,
                    "talhao_id": a.talhao_id,
                    "severidade": a.severidade,
                    "mensagem": a.mensagem,
                    "lido": a.lido,
                    "criado_em": a.criado_em,
                }
                for a in itens
            ]
        }

    @_segura
    def listar_diagnosticos(
        talhao_id: int | None = None, severidade: str | None = None, limite: int = 15
    ) -> dict:
        """Diagnósticos mais recentes (vigor NDVI, estresse hídrico, nutrição do solo e pragas por
        armadilha). Filtros opcionais: `talhao_id` e `severidade` (BAIXA, MEDIA ou ALTA)."""
        sev = Severidade(severidade.upper()) if severidade else None
        return {
            "diagnosticos": diagnostico.listar(
                db, talhao_id=talhao_id, severidade=sev, limite=_limite(limite)
            )
        }

    @_segura
    def listar_pragas() -> dict:
        """Pragas do milho cadastradas, com os limiares de alerta, controle e dano."""
        return {"pragas": [_linha(p) for p in pragasService.listar_pragas(db)]}

    @_segura
    def listar_produtos() -> dict:
        """Produtos do catálogo (corretivos, sementes, defensivos) com classe, dose mínima e máxima,
        unidade e carência."""
        return {"produtos": [_linha(p) for p in produtosService.listar_produtos(db)]}

    def _exibir(montar, *args) -> dict:
        """Monta o painel (dados do banco), guarda a especificação e devolve só um resumo ao modelo."""
        if len(paineis) >= LIMITE_PAINEIS:
            return {"erro": f"Já há {LIMITE_PAINEIS} painéis nesta resposta; não mostre mais."}
        spec, resumo = montar(db, *args)
        paineis.append(_limpar(spec))
        return {"mostrado": spec["tipo"], "titulo": spec["titulo"], **resumo}

    @_segura
    def mostrar_grafico(metrica: str, talhao_ids: list[int] | None = None, titulo: str | None = None) -> dict:
        """Mostra ao usuário, no painel ao lado do chat, um gráfico de linhas animado. `metrica` é
        'ndvi', 'balanco_hidrico' (por talhão), 'temperatura' ou 'chuva' (clima da fazenda).
        `talhao_ids` escolhe até 4 talhões (vazio = todos). Os dados vêm do banco; você recebe só um
        resumo em números para comentar. Use quando um gráfico ajudar a responder."""
        return _exibir(paineis_svc.grafico, metrica, talhao_ids, titulo)

    @_segura
    def mostrar_grafico_analitico(
        talhao_ids: list[int] | None = None,
        metrica: str = "ndvi",
        complemento: str | None = "chuva",
        de: str | None = None,
        ate: str | None = None,
        anotar: bool = True,
        notas: list[str] | None = None,
    ) -> dict:
        """Mostra no painel um gráfico animado de análise: linhas por talhão (`metrica` 'ndvi' ou
        'balanco_hidrico') junto com o clima da fazenda (`complemento`: 'chuva' em barras, 'temperatura'
        ou vazio), com caixas de anotação nos eventos (chuvas fortes, pico e maior queda de NDVI, pragas
        altas, plantio). `talhao_ids` escolhe até 4 talhões; `de` e `ate` em AAAA-MM-DD. Use quando o
        usuário pedir gráfico com chuva, anotações, marcações ou análise. As anotações saem dos dados;
        você pode somar até 3 `notas` no formato 'AAAA-MM-DD: texto curto', só com fatos do resumo
        devolvido. A chuva é de UMA estação para a fazenda toda: nunca a trate como diferente entre
        talhões. Depois de chamar, analise o gráfico no texto com os números do resumo, sem afirmar
        causa (fale em coincidência ou hipótese)."""
        return _exibir(
            paineis_svc.grafico_analitico, talhao_ids, metrica, complemento, de, ate, anotar, notas
        )

    @_segura
    def mostrar_galeria_pragas(
        talhao_id: int | None = None, praga: str | None = None, severidade: str | None = None, limite: int = 4
    ) -> dict:
        """Mostra no painel as fotos de armadilha com as caixas de detecção das pragas, das contagens
        mais altas para as mais baixas. Filtros opcionais: `talhao_id`, `praga` (parte do nome) e
        `severidade` (BAIXA, MEDIA ou ALTA). `limite` até 6 fotos. Use quando pedirem para ver pragas."""
        return _exibir(paineis_svc.galeria_pragas, talhao_id, praga, severidade, limite)

    @_segura
    def mostrar_comparativo(talhao_a: int, talhao_b: int) -> dict:
        """Mostra no painel dois talhões lado a lado: indicadores (NDVI médio, pico, pragas, produtividade)
        com o melhor destacado e a curva de NDVI dos dois. Use para perguntas do tipo 'por que um foi
        melhor que o outro'. Obtenha os ids com resumo_geral."""
        return _exibir(paineis_svc.comparativo, talhao_a, talhao_b)

    return [
        resumo_geral,
        consultar_talhao,
        serie_ndvi,
        clima_diario,
        listar_alertas,
        listar_diagnosticos,
        listar_pragas,
        listar_produtos,
        mostrar_grafico,
        mostrar_grafico_analitico,
        mostrar_galeria_pragas,
        mostrar_comparativo,
    ]


__all__ = ["criar_tools"]
