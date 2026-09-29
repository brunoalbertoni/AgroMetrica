"""Dados sintéticos e determinísticos no formato do FarmLab, usados quando os arquivos reais
não estão em data/raw/farmlab (ou com --demo).

Safra de milho 2023/24 com 4 talhões: Grão e Silagem, cada um em manejo 4.0 e convencional.
"""

import math
import random
from datetime import date, datetime, timedelta

import cv2
import numpy as np

SEMENTE = 2024
INICIO_CLIMA = datetime(2023, 10, 1)
FIM_CLIMA = datetime(2024, 3, 31, 23)
PRIMEIRA_NDVI = date(2023, 10, 10)
DATAS_NDVI = [PRIMEIRA_NDVI + timedelta(days=3 * i) for i in range(49)]

# (nome, sistema, finalidade, área, NDVI de pico, produtividade kg/ha, data da colheita)
TALHOES = [
    ("Grão 4.0", "AGRO_4_0", "GRAO", 12.40, 0.87, 11850, date(2024, 3, 20)),
    ("Grão Convencional", "CONVENCIONAL", "GRAO", 11.85, 0.77, 9720, date(2024, 3, 20)),
    ("Silagem 4.0", "AGRO_4_0", "SILAGEM", 8.60, 0.85, 58400, date(2024, 2, 20)),
    ("Silagem Convencional", "CONVENCIONAL", "SILAGEM", 8.35, 0.76, 51200, date(2024, 2, 20)),
]

PRAGAS = [
    # nome, científico, alerta, controle, dano (adultos por armadilha por semana)
    ("Lagarta-do-cartucho", "Spodoptera frugiperda", 3, 6, 10),
    ("Cigarrinha-do-milho", "Dalbulus maidis", 5, 10, 20),
    ("Percevejo-barriga-verde", "Diceraeus melacanthus", 2, 4, 8),
]

# nome comercial genérico, ingrediente ativo, classe, dose mín, dose máx, unidade, carência, pragas
PRODUTOS = [
    (
        "Inseticida Diamida 200 SC",
        "Clorantraniliprole",
        "INSETICIDA",
        100,
        150,
        "mL/ha",
        30,
        ["Lagarta-do-cartucho"],
    ),
    (
        "Inseticida Espinosina 480 SC",
        "Espinosade",
        "INSETICIDA",
        80,
        120,
        "mL/ha",
        14,
        ["Lagarta-do-cartucho"],
    ),
    (
        "Inseticida Neonicotinoide 700 WG",
        "Acetamiprido",
        "INSETICIDA",
        150,
        250,
        "g/ha",
        21,
        ["Cigarrinha-do-milho", "Percevejo-barriga-verde"],
    ),
    ("Fungicida Triazol 250 EC", "Tebuconazol", "FUNGICIDA", 0.5, 0.75, "L/ha", 30, []),
    ("Calcário Dolomítico", "CaCO3 + MgCO3", "CORRETIVO", 1, 3, "t/ha", None, []),
    ("Cloreto de Potássio", "KCl 60% K2O", "FERTILIZANTE", 100, 150, "kg/ha", None, []),
]

_ORIGEM = (-50.1000, -24.9500)  # lon, lat
_LADO = 0.0040


def geometria(indice: int) -> str:
    lon0 = _ORIGEM[0] + (indice % 2) * (_LADO + 0.0004)
    lat0 = _ORIGEM[1] + (indice // 2) * (_LADO + 0.0004)
    pts = [
        (lon0, lat0),
        (lon0 + _LADO, lat0),
        (lon0 + _LADO, lat0 + _LADO),
        (lon0, lat0 + _LADO),
        (lon0, lat0),
    ]
    return "POLYGON((" + ", ".join(f"{x:.6f} {y:.6f}" for x, y in pts) + "))"


def centro(indice: int) -> tuple[float, float]:
    lon0 = _ORIGEM[0] + (indice % 2) * (_LADO + 0.0004)
    lat0 = _ORIGEM[1] + (indice // 2) * (_LADO + 0.0004)
    return lat0 + _LADO / 2, lon0 + _LADO / 2


def _seco(d: datetime) -> bool:
    """Veranico de janeiro e fim de março sem chuva (gera déficit hídrico)."""
    return date(2024, 1, 5) <= d.date() <= date(2024, 1, 28) or d.date() >= date(2024, 3, 22)


def clima() -> list[dict]:
    rnd = random.Random(SEMENTE)
    linhas, dias_chuva = [], {}
    atual = INICIO_CLIMA
    while atual <= FIM_CLIMA:
        dia = atual.date()
        if dia not in dias_chuva:
            chove = not _seco(atual) and rnd.random() < 0.33
            dias_chuva[dia] = (rnd.randint(14, 19), rnd.randint(1, 4), rnd.uniform(2, 9)) if chove else None
        fase = math.sin((atual.hour - 9) / 24 * 2 * math.pi)
        extra_seca = 2.5 if _seco(atual) else 0
        temp = 22.5 + 6 * fase + extra_seca + rnd.gauss(0, 0.8)
        umidade = max(30, min(98, 74 - (temp - 22) * 3.2 - extra_seca * 3 + rnd.gauss(0, 3)))
        vento = max(0.5, 7 + 4.5 * fase + rnd.gauss(0, 1.5))
        radiacao = max(0.0, 850 * math.sin((atual.hour - 6) / 12 * math.pi)) if 6 <= atual.hour <= 18 else 0.0
        etp = round(radiacao / 850 * (0.42 if _seco(atual) else 0.30), 3)
        chuva = 0.0
        evento = dias_chuva[dia]
        if evento and evento[0] <= atual.hour < evento[0] + evento[1]:
            chuva = round(evento[2] * rnd.uniform(0.6, 1.4), 1)
            umidade = min(98, umidade + 20)
        linhas.append(
            {
                "data_hora": atual,
                "temp_min": round(temp - 0.6, 1),
                "temp_med": round(temp, 1),
                "temp_max": round(temp + 0.6, 1),
                "chuva_mm": chuva,
                "umidade_med": round(umidade, 1),
                "vento_kmh": round(vento, 1),
                "radiacao": round(radiacao, 1),
                "etp_mm": etp,
            }
        )
        atual += timedelta(hours=1)
    return linhas


def ndvi(indice: int) -> list[dict]:
    rnd = random.Random(SEMENTE + indice)
    _, sistema, finalidade, _, pico, _, colheita = TALHOES[indice]
    linhas = []
    for d in DATAS_NDVI:
        dias = (d - PRIMEIRA_NDVI).days
        valor = 0.22 + (pico - 0.22) / (1 + math.exp(-(dias - 38) / 7))
        if dias > 105:
            valor -= (dias - 105) * (0.0045 if sistema == "AGRO_4_0" else 0.0060)
        if finalidade == "SILAGEM" and d >= colheita:
            valor = 0.25
        if indice == 1 and date(2023, 12, 15) <= d <= date(2023, 12, 24):  # ataque de lagarta no convencional
            valor *= 0.80
        if indice == 3 and d == DATAS_NDVI[-1]:  # queda na última leitura → diagnóstico de vigor
            valor = linhas[-1]["ndvi_medio"] * 0.80
        valor = round(max(0.1, min(0.95, valor + rnd.gauss(0, 0.008))), 3)
        linhas.append(
            {
                "data": d,
                "ndvi_medio": valor,
                "ndvi_min": round(max(0.05, valor - rnd.uniform(0.10, 0.18)), 3),
                "ndvi_max": round(min(0.98, valor + rnd.uniform(0.04, 0.08)), 3),
            }
        )
    return linhas


def solo(indice: int) -> list[dict]:
    rnd = random.Random(SEMENTE + 100 + indice)
    _, sistema, *_ = TALHOES[indice]
    lat_c, lon_c = centro(indice)
    corrigido = sistema == "AGRO_4_0"
    linhas = []
    for p in range(6):
        ph = rnd.uniform(5.5, 6.1) if corrigido else rnd.uniform(4.6, 5.4)
        v = rnd.uniform(58, 72) if corrigido else rnd.uniform(38, 56)
        linhas.append(
            {
                "ponto": f"P{p + 1}",
                "zona": 1 + p // 3,
                "lat": round(lat_c + rnd.uniform(-0.0015, 0.0015), 6),
                "lon": round(lon_c + rnd.uniform(-0.0015, 0.0015), 6),
                "data_coleta": date(2023, 9, 15),
                "ph": round(ph, 2),
                "mo": round(rnd.uniform(28, 42), 1),
                "ctc": round(rnd.uniform(9, 14), 2),
                "p": round(rnd.uniform(14, 30) if corrigido else rnd.uniform(8, 18), 1),
                "k": round(rnd.uniform(0.25, 0.45) if corrigido else rnd.uniform(0.10, 0.24), 2),
                "ca": round(rnd.uniform(3.5, 6), 2),
                "mg": round(rnd.uniform(1.0, 2.2), 2),
                "s": round(rnd.uniform(6, 14), 1),
                "b": round(rnd.uniform(0.2, 0.6), 2),
                "zn": round(rnd.uniform(1.0, 3.5), 2),
                "mn": round(rnd.uniform(8, 25), 1),
                "cu": round(rnd.uniform(0.8, 2.5), 2),
                "v_pct": round(v, 1),
            }
        )
    return linhas


def armadilhas(indice: int) -> list[dict]:
    """Leituras semanais de armadilha. Só a lagarta tem foto (com bounding boxes)."""
    rnd = random.Random(SEMENTE + 200 + indice)
    _, sistema, *_ = TALHOES[indice]
    convencional = sistema == "CONVENCIONAL"
    eventos = []
    for semana in range(19):
        dia = datetime(2023, 10, 20, 8) + timedelta(weeks=semana)
        curva = math.exp(-((semana - 9) ** 2) / 10)
        lagarta = round((12.5 if convencional else 6.2) * curva + rnd.uniform(0, 1.2))
        cigarrinha = round(
            (13 if convencional else 7) * math.exp(-((semana - 13) ** 2) / 8) + rnd.uniform(0, 2)
        )
        eventos.append({"data": dia, "praga": "Lagarta-do-cartucho", "contagem": lagarta, "foto": True})
        eventos.append({"data": dia, "praga": "Cigarrinha-do-milho", "contagem": cigarrinha, "foto": False})
    return eventos


def imagem_armadilha(contagem: int, semente: int) -> tuple[np.ndarray, list[dict]]:
    """Cartão adesivo amarelo com insetos desenhados; devolve a imagem BGR e as caixas normalizadas."""
    rnd = random.Random(semente)
    largura, altura = 640, 480
    img = np.full((altura, largura, 3), (40, 215, 245), dtype=np.uint8)
    for x in range(0, largura, 40):
        cv2.line(img, (x, 0), (x, altura), (30, 190, 220), 1)
    for y in range(0, altura, 40):
        cv2.line(img, (0, y), (largura, y), (30, 190, 220), 1)
    caixas = []
    for _ in range(int(contagem)):
        w, h = rnd.randint(28, 46), rnd.randint(14, 22)
        cx, cy = rnd.randint(40, largura - 40), rnd.randint(40, altura - 40)
        angulo = rnd.randint(0, 180)
        cv2.ellipse(img, (cx, cy), (w // 2, h // 2), angulo, 0, 360, (35, 45, 70), -1)
        cv2.ellipse(img, (cx, cy), (w // 4, h // 3), angulo, 0, 360, (60, 80, 110), -1)
        lado = max(w, h) + 8
        x0, y0 = max(0, cx - lado // 2), max(0, cy - lado // 2)
        caixas.append(
            {
                "x": round(x0 / largura, 4),
                "y": round(y0 / altura, 4),
                "w": round(min(lado, largura - x0) / largura, 4),
                "h": round(min(lado, altura - y0) / altura, 4),
                "rotulo": "Lagarta-do-cartucho",
                "confianca": round(rnd.uniform(0.78, 0.97), 2),
            }
        )
    return img, caixas
