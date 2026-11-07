"""Cadeia de modelos do Gemini e controle de cota.

A cota gratuita é por modelo e por dia. Quando um modelo devolve 429, ele fica "bloqueado" até a hora
em que o Google diz que volta, e as próximas chamadas já começam pelo seguinte, sem gastar uma requisição
só para descobrir que a cota acabou. O estado fica em memória: reiniciar o servidor zera o bloqueio, e a
primeira chamada descobre de novo.
"""

import logging
import threading
import time

from google.genai import errors

from app.core.config import settings

log = logging.getLogger("assistente")

ESPERA_PADRAO_S = 60  # quando o erro 429 não informa quanto esperar
ESPERA_MAXIMA_S = 24 * 3600
ESPERA_MODELO_INEXISTENTE_S = 3600

_bloqueados: dict[str, float] = {}  # modelo -> instante (time.time) em que volta a valer
_trava = threading.Lock()


def cadeia(leve_primeiro: bool = False) -> list[str]:
    """Modelos em ordem de preferência, sem repetir. Tarefas simples (classificar) começam pelo leve."""
    principal = [settings.gemini_modelo]
    leve = [settings.gemini_modelo_leve]
    reserva = [m.strip() for m in settings.gemini_modelos_reserva.split(",") if m.strip()]
    ordem = leve + reserva + principal if leve_primeiro else principal + leve + reserva
    return list(dict.fromkeys(m for m in ordem if m))


def disponiveis(leve_primeiro: bool = False) -> list[str]:
    """Modelos da cadeia que não estão bloqueados por cota agora."""
    agora = time.time()
    with _trava:
        return [m for m in cadeia(leve_primeiro) if _bloqueados.get(m, 0) <= agora]


def bloquear(modelo: str, segundos: float) -> None:
    segundos = max(1.0, min(segundos, ESPERA_MAXIMA_S))
    with _trava:
        _bloqueados[modelo] = time.time() + segundos
    log.warning("Modelo %s sem cota: pulando por %.0f s", modelo, segundos)


def segundos_para_voltar() -> float:
    """Menor espera até algum modelo da cadeia voltar a valer (0 se algum já está livre)."""
    agora = time.time()
    with _trava:
        restantes = [max(0.0, _bloqueados.get(m, 0) - agora) for m in cadeia()]
    return min(restantes) if restantes else 0.0


def limpar() -> None:
    with _trava:
        _bloqueados.clear()


def segundos_do_erro(erro: errors.APIError) -> float:
    """Tempo de espera pedido pelo Google num 429 (campo retryDelay, ex.: '55739s' ou '12.5s')."""
    detalhes = erro.details if isinstance(getattr(erro, "details", None), dict) else {}
    for item in (detalhes.get("error") or {}).get("details") or []:
        atraso = item.get("retryDelay") if isinstance(item, dict) else None
        if isinstance(atraso, str) and atraso.endswith("s"):
            try:
                return float(atraso[:-1])
            except ValueError:
                pass
    return ESPERA_PADRAO_S


def tratar_cota(modelo: str, erro: errors.APIError) -> bool:
    """Se o erro é de cota (429) ou de modelo inexistente (404), bloqueia o modelo e devolve True."""
    if erro.code == 429:
        bloquear(modelo, segundos_do_erro(erro))
        return True
    if erro.code == 404:
        bloquear(modelo, ESPERA_MODELO_INEXISTENTE_S)
        return True
    return False


def descricao_espera(segundos: float) -> str:
    """Texto curto para a mensagem de erro: 'cerca de 15 h', 'cerca de 40 min', 'menos de 1 min'."""
    if segundos >= 3600:
        return f"cerca de {round(segundos / 3600)} h"
    if segundos >= 60:
        return f"cerca de {round(segundos / 60)} min"
    return "menos de 1 min"
