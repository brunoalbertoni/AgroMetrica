"""Agente do AgroMétrica: conversa com o usuário via Gemini e, quando a pergunta pede dados,
chama tools de consulta ao banco (somente leitura — ver assistenteTools). Nada é criado,
alterado ou apagado.

A cota gratuita do Gemini é por modelo e por dia, então o agente gasta pouco e tem reserva:
- um resumo dos talhões vai já no prompt (poupa a chamada `resumo_geral`);
- o modelo é orientado a pedir várias tools de uma vez (menos idas e vindas);
- respostas iguais em poucos minutos saem de um cache;
- se um modelo estoura a cota (429), o próximo da cadeia assume (ver assistenteModelos).
"""

import copy
import hashlib
import json
import logging
import time
from datetime import date

import httpx
from google import genai
from google.genai import errors, types
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.assistente import assistenteModelos
from app.services.assistente.assistenteTools import criar_tools
from app.services.dashboard import dashboardService

log = logging.getLogger("assistente")

TENTATIVAS = 2  # por modelo, para 500/503/504
ESPERA_S = 2
TIMEOUT_MS = 20_000  # por chamada ao Gemini; sem isso a requisição pode ficar pendente por minutos
MAX_CHAMADAS_TOOLS = 4
CACHE_TTL_S = 300
CACHE_MAX = 100

_cache: dict[str, tuple[float, str, list[dict]]] = {}


class ErroAssistente(Exception):
    """Falha ao consultar o modelo (cota estourada ou outro erro do provedor)."""

    def __init__(self, mensagem: str, status: int = 502):
        super().__init__(mensagem)
        self.status = status


class _SemCota(Exception):
    """O modelo atual estourou a cota (ou não existe): vale tentar o próximo da cadeia."""


def limpar_cache() -> None:
    _cache.clear()


def _retrato(db: Session) -> str:
    """Resumo compacto dos talhões e totais, para o modelo não precisar chamar `resumo_geral`."""
    r = dashboardService.resumo(db)
    c = r["cards"]
    linhas = ["id | nome | sistema | finalidade | área (ha) | último NDVI | pior alerta aberto"]
    for t in r["talhoes"]:
        linhas.append(
            f"{t['id']} | {t['nome']} | {t['sistema']} | {t['finalidade']} | {t['area_ha']} | "
            f"{t.get('ultimo_ndvi')} | {t.get('severidade') or 'nenhum'}"
        )
    totais = (
        f"Totais: {c['talhoes']} talhões, {c['area_total_ha']} ha, {c['alertas_abertos']} alertas abertos "
        f"({c['alertas_altos']} altos), {c['diagnosticos']} diagnósticos, "
        f"NDVI médio atual {c['ndvi_medio_atual']}."
    )
    return "\n".join([*linhas, totais])


def _instrucao(hoje: date, retrato: str) -> str:
    return (
        "Você é o assistente agronômico do AgroMétrica, um sistema de monitoramento de talhões de "
        "milho. Responda em português do Brasil, de forma curta e clara, em markdown.\n"
        f"Data de hoje: {hoje.isoformat()}.\n"
        "Retrato atual dos talhões (use estes ids e valores; NÃO chame resumo_geral só para isso):\n"
        f"{retrato}\n"
        "Para o resto (NDVI ao longo do tempo, clima, solo, alertas, diagnósticos, pragas, produtos) use as "
        "ferramentas de consulta. Se precisar de mais de uma, peça todas de uma só vez, em paralelo, em "
        "vez de uma por vez. Para conversa que não precisa de dados, responda direto, sem ferramentas.\n"
        "Todo número que você citar precisa vir do retrato ou do resultado das ferramentas; nunca invente "
        "valores. Se não trouxerem o que foi perguntado, diga que não tem essa informação.\n"
        "Não afirme causas que os dados não mostram: quando duas coisas aparecem juntas (ex.: NDVI baixo "
        "e pragas), diga que coincidem ou que é uma hipótese a investigar, nunca que uma causou a outra.\n"
        "Há ferramentas mostrar_* que abrem um painel visual animado ao lado do chat (gráfico, fotos de "
        "pragas com caixas de detecção, comparativo de talhões). Use-as quando ajudarem a responder: "
        "por exemplo, ao comparar talhões, mostrar_comparativo; ao falar de evolução, mostrar_grafico; "
        "ao pedirem para ver pragas, mostrar_galeria_pragas. No máximo 2 painéis por resposta, e comente "
        "no texto o que o painel mostra, sem repetir todos os números.\n"
        "As ferramentas só leem dados; você não consegue criar, alterar nem apagar nada no sistema, "
        "e deve dizer isso se pedirem. Sugestões de manejo são sugestões e precisam de validação de "
        "um responsável técnico — deixe isso claro quando sugerir algo."
    )


def _conteudos(mensagem: str, historico: list[dict]) -> list[types.Content]:
    conteudos = []
    for item in historico:
        papel = "model" if item.get("papel") == "modelo" else "user"
        conteudos.append(types.Content(role=papel, parts=[types.Part(text=item.get("texto", ""))]))
    conteudos.append(types.Content(role="user", parts=[types.Part(text=mensagem)]))
    return conteudos


def _chave_cache(mensagem: str, historico: list[dict]) -> str:
    bruto = json.dumps([mensagem, historico, date.today().isoformat()], ensure_ascii=False, sort_keys=True)
    return hashlib.sha1(bruto.encode("utf-8")).hexdigest()


def _mensagem_sem_cota() -> str:
    espera = assistenteModelos.descricao_espera(assistenteModelos.segundos_para_voltar())
    return f"Os modelos do Gemini atingiram a cota gratuita de hoje. Volta em {espera}."


def _gerar(cliente: genai.Client, modelo: str, conteudos: list, config: types.GenerateContentConfig):
    """Uma resposta de um modelo, com novas tentativas para erros 500/503/504.

    Levanta _SemCota se a cota acabou (o chamador tenta o próximo modelo) e ErroAssistente nos demais casos.
    """
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            return cliente.models.generate_content(model=modelo, contents=conteudos, config=config)
        except httpx.TimeoutException as erro:
            log.warning("Gemini sem resposta em %d ms (%s)", TIMEOUT_MS, modelo)
            raise ErroAssistente("O Gemini demorou demais para responder. Tente de novo.", 504) from erro
        except errors.APIError as erro:
            log.warning("Gemini %s (%s), tentativa %d/%d: %s", erro.code, modelo, tentativa, TENTATIVAS, erro)
            if assistenteModelos.tratar_cota(modelo, erro):
                raise _SemCota from erro
            if erro.code in (500, 503, 504):
                if tentativa < TENTATIVAS:
                    time.sleep(ESPERA_S)
                    continue
                raise ErroAssistente(
                    "O Gemini está sobrecarregado agora. Tente de novo em instantes.", 503
                ) from erro
            raise ErroAssistente("O assistente não conseguiu responder agora. Tente novamente.") from erro
    raise ErroAssistente("O assistente não conseguiu responder agora. Tente novamente.")  # inalcançável


def responder(db: Session, mensagem: str, historico: list[dict]) -> tuple[str, list[dict]]:
    """Pergunta ao Gemini com as tools; o SDK executa as chamadas de função sozinho.

    Devolve (texto, painéis): os painéis são as especificações que as tools `mostrar_*` registraram.
    """
    if not settings.gemini_api_key:
        raise ErroAssistente("Assistente indisponível: defina GEMINI_API_KEY no .env.", status=503)

    chave = _chave_cache(mensagem, historico)
    guardado = _cache.get(chave)
    if guardado and time.time() - guardado[0] < CACHE_TTL_S:
        return guardado[1], copy.deepcopy(guardado[2])

    modelos = assistenteModelos.disponiveis()
    if not modelos:
        raise ErroAssistente(_mensagem_sem_cota(), 429)

    paineis: list[dict] = []
    config = types.GenerateContentConfig(
        system_instruction=_instrucao(date.today(), _retrato(db)),
        tools=criar_tools(db, paineis),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(
            maximum_remote_calls=MAX_CHAMADAS_TOOLS
        ),
    )
    cliente = genai.Client(
        api_key=settings.gemini_api_key,
        http_options=types.HttpOptions(
            timeout=TIMEOUT_MS,
            retry_options=types.HttpRetryOptions(attempts=1),  # o retry é feito aqui, com limite total
        ),
    )
    conteudos = _conteudos(mensagem, historico)
    for modelo in modelos:
        paineis.clear()  # uma tentativa abandonada no meio não pode deixar painéis duplicados
        try:
            resposta = _gerar(cliente, modelo, conteudos, config)
        except _SemCota:
            continue
        break
    else:
        raise ErroAssistente(_mensagem_sem_cota(), 429)

    if modelo != settings.gemini_modelo:
        log.info("Resposta gerada pelo modelo de reserva %s", modelo)
    texto = resposta.text or "Não consegui montar uma resposta. Tente reformular a pergunta."
    if resposta.text:  # erro ou resposta vazia não entram no cache
        if len(_cache) >= CACHE_MAX:
            _cache.pop(next(iter(_cache)))
        _cache[chave] = (time.time(), texto, copy.deepcopy(paineis))
    return texto, paineis
