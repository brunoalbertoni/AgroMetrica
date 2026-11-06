"""Geometria simples em WKT (lon lat), suficiente para ligar pontos de máquina, armadilhas e
imagens de satélite aos talhões sem depender de uma biblioteca GIS."""

import math
import re

_RAIO_TERRA = 6378137.0
_M2_POR_GRAU2_NO_EQUADOR = (math.pi / 180 * _RAIO_TERRA) ** 2

Anel = list[tuple[float, float]]


def aneis(wkt: str | None) -> list[Anel]:
    """Anéis externos de POLYGON / MULTIPOLYGON (buracos são ignorados; os talhões não têm)."""
    if not wkt:
        return []
    poligonos = re.findall(r"\(\(([^()]+)\)", wkt)
    return [[tuple(map(float, par.split()[:2])) for par in p.split(",")] for p in poligonos]


def para_polygon(wkt: str | None) -> str | None:
    """MULTIPOLYGON → POLYGON do maior anel, o formato que o mapa do frontend lê."""
    lista = aneis(wkt)
    if not lista:
        return None
    maior = max(lista, key=lambda a: abs(_area_graus2(a)))
    return "POLYGON((" + ", ".join(f"{lon} {lat}" for lon, lat in maior) + "))"


def contem(anel: Anel, lon: float, lat: float) -> bool:
    """Ponto dentro do anel (ray casting)."""
    dentro = False
    for i in range(len(anel)):
        x1, y1 = anel[i]
        x2, y2 = anel[i - 1]
        if (y1 > lat) != (y2 > lat) and lon < (x2 - x1) * (lat - y1) / (y2 - y1) + x1:
            dentro = not dentro
    return dentro


def centro(wkt: str) -> tuple[float, float] | None:
    """Média dos vértices do primeiro anel (os trechos de máquina são polígonos pequenos)."""
    lista = aneis(wkt)
    if not lista:
        return None
    anel = lista[0]
    return sum(p[0] for p in anel) / len(anel), sum(p[1] for p in anel) / len(anel)


def _area_graus2(anel: Anel) -> float:
    return sum(x1 * y2 - x2 * y1 for (x1, y1), (x2, y2) in zip(anel, anel[1:] + anel[:1], strict=True)) / 2


def area_ha(wkt: str | None) -> float | None:
    """Área aproximada (projeção equiretangular local), boa para talhões de dezenas de hectares."""
    lista = aneis(wkt)
    if not lista:
        return None
    total = 0.0
    for anel in lista:
        lat_media = sum(p[1] for p in anel) / len(anel)
        total += abs(_area_graus2(anel)) * _M2_POR_GRAU2_NO_EQUADOR * math.cos(math.radians(lat_media))
    return total / 10_000


def mercator_para_lonlat(x: float, y: float) -> tuple[float, float]:
    """EPSG:3857 → EPSG:4326."""
    lon = math.degrees(x / _RAIO_TERRA)
    lat = math.degrees(2 * math.atan(math.exp(y / _RAIO_TERRA)) - math.pi / 2)
    return lon, lat


class Localizador:
    """Encontra o talhão que contém um ponto."""

    def __init__(self, talhoes: dict[int, str | None]):
        self._aneis = [(tid, anel) for tid, wkt in talhoes.items() for anel in aneis(wkt)]

    def talhao(self, lon: float, lat: float) -> int | None:
        return next((tid for tid, anel in self._aneis if contem(anel, lon, lat)), None)
