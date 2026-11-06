"""Agente do AgroMétrica: conversa com o usuário via Gemini e, quando a pergunta pede dados,
chama tools de consulta ao banco (somente leitura — ver assistente_tools). Nada é criado,
alterado ou apagado."""

import logging
import time
from datetime import date

import httpx
from google import genai
from google.genai import errors, types
from sqlalchemy.orm import Session

from app.core.config import settings
from app.services.assistente.assistenteTools import criar_tools

log = logging.getLogger("assistente")

TENTATIVAS = 2
ESPERA_S = 2
TIMEOUT_MS = 20_000  # por chamada ao Gemini; sem isso a requisição pode ficar pendente por minutos
MAX_CHAMADAS_TOOLS = 6


class ErroAssistente(Exception):
    """Falha ao consultar o modelo (cota estourada ou outro erro do provedor)."""

    def __init__(self, mensagem: str, status: int = 502):
        super().__init__(mensagem)
        self.status = status


def _instrucao(hoje: date) -> str:
    return (
        "Você é o assistente agronômico do AgroMétrica, um sistema de monitoramento de talhões de "
        "milho. Responda em português do Brasil, de forma curta e clara, em markdown.\n"
        f"Data de hoje: {hoje.isoformat()}.\n"
        "Você NÃO tem os dados do sistema de cabeça: use as ferramentas de consulta para buscá-los "
        "sempre que a pergunta depender deles (talhões, NDVI, clima, solo, alertas, diagnósticos, "
        "pragas, produtos). Comece por resumo_geral se precisar descobrir ids de talhões. "
        "Para conversa que não precisa de dados, responda direto, sem chamar ferramentas.\n"
        "Todo número que você citar precisa vir do resultado das ferramentas; nunca invente valores. "
        "Se as ferramentas não trouxerem o que foi perguntado, diga que não tem essa informação.\n"
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


def responder(db: Session, mensagem: str, historico: list[dict]) -> str:
    """Pergunta ao Gemini com as tools de consulta; o SDK executa as chamadas de função sozinho."""
    if not settings.gemini_api_key:
        raise ErroAssistente("Assistente indisponível: defina GEMINI_API_KEY no .env.", status=503)

    config = types.GenerateContentConfig(
        system_instruction=_instrucao(date.today()),
        tools=criar_tools(db),
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
    for tentativa in range(1, TENTATIVAS + 1):
        try:
            resposta = cliente.models.generate_content(
                model=settings.gemini_modelo, contents=_conteudos(mensagem, historico), config=config
            )
            break
        except httpx.TimeoutException as erro:
            log.warning("Gemini sem resposta em %d ms (%s)", TIMEOUT_MS, settings.gemini_modelo)
            raise ErroAssistente("O Gemini demorou demais para responder. Tente de novo.", 504) from erro
        except errors.APIError as erro:
            log.warning(
                "Gemini %s (%s), tentativa %d/%d: %s",
                erro.code,
                settings.gemini_modelo,
                tentativa,
                TENTATIVAS,
                erro,
            )
            if erro.code in (500, 503, 504) and tentativa < TENTATIVAS:
                time.sleep(ESPERA_S)
                continue
            if erro.code == 429:
                raise ErroAssistente(
                    "Limite gratuito do Gemini atingido. Tente de novo em um minuto.", 429
                ) from erro
            if erro.code == 404:
                raise ErroAssistente(
                    f"Modelo '{settings.gemini_modelo}' indisponível. Ajuste GEMINI_MODELO no .env."
                ) from erro
            if erro.code in (500, 503, 504):
                raise ErroAssistente(
                    "O Gemini está sobrecarregado agora. Tente de novo em instantes.", 503
                ) from erro
            raise ErroAssistente("O assistente não conseguiu responder agora. Tente novamente.") from erro

    return resposta.text or "Não consegui montar uma resposta. Tente reformular a pergunta."
