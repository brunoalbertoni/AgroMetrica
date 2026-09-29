"""Importação de CSV/XLSX (clima Metos, solo Cropman, NDVI OneSoil, colheita EKOS).

Cada tipo tem um mapa de colunas: nome canônico (coluna do banco) → apelidos aceitos no arquivo.
Os cabeçalhos são normalizados (minúsculas, sem acento, sem unidade entre colchetes) antes de comparar.
"""

import io
import re
import unicodedata
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime

import pandas as pd
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LeituraClima, LeituraSolo, MetricaTalhao, Talhao, Upload
from app.models.enums import TipoUpload
from app.services.upsert import upsert


@dataclass
class Coluna:
    apelidos: tuple[str, ...]
    obrigatoria: bool = False
    tipo: str = "float"  # float | int | str | data | datahora
    fator: dict[str, float] = field(default_factory=dict)  # apelido → fator de conversão


_TALHAO = Coluna(
    ("talhao_id", "talhao", "field_id", "field", "field_name", "nome_talhao", "talhao_nome"), True, "str"
)

MAPAS: dict[TipoUpload, dict[str, Coluna]] = {
    TipoUpload.CLIMA: {
        "data_hora": Coluna(
            ("data_hora", "datahora", "date_time", "datetime", "data", "date", "timestamp"), True, "datahora"
        ),
        "temp_med": Coluna(
            (
                "temp_med",
                "temperatura_media",
                "temperatura",
                "hc_air_temperature_avg",
                "air_temperature_avg",
                "temp_avg",
                "temperature_avg",
            ),
            True,
        ),
        "temp_min": Coluna(
            ("temp_min", "temperatura_minima", "hc_air_temperature_min", "air_temperature_min")
        ),
        "temp_max": Coluna(
            ("temp_max", "temperatura_maxima", "hc_air_temperature_max", "air_temperature_max")
        ),
        "chuva_mm": Coluna(
            ("chuva_mm", "chuva", "precipitacao", "precipitation_sum", "precipitation", "rain", "rainfall"),
            True,
        ),
        "umidade_med": Coluna(
            (
                "umidade_med",
                "umidade",
                "umidade_relativa",
                "hc_relative_humidity_avg",
                "relative_humidity_avg",
                "humidity",
            )
        ),
        "vento_kmh": Coluna(
            ("vento_kmh", "vento", "vento_ms", "wind_speed_avg", "wind_speed"),
            fator={"vento_ms": 3.6, "wind_speed_avg": 3.6, "wind_speed": 3.6},
        ),
        "radiacao": Coluna(("radiacao", "solar_radiation_avg", "solar_radiation", "radiation")),
        "etp_mm": Coluna(
            ("etp_mm", "etp", "eto", "eto_mm", "et0", "evapotranspiration", "evapotranspiracao")
        ),
    },
    TipoUpload.SOLO: {
        "talhao_id": _TALHAO,
        "ponto": Coluna(("ponto", "point", "sample", "amostra", "sample_id", "ponto_id"), True, "str"),
        "data_coleta": Coluna(
            ("data_coleta", "data", "date", "sampling_date", "collection_date"), True, "data"
        ),
        "zona": Coluna(("zona", "zone", "management_zone"), tipo="int"),
        "lat": Coluna(("lat", "latitude")),
        "lon": Coluna(("lon", "lng", "longitude")),
        "ph": Coluna(("ph", "ph_cacl2", "ph_h2o", "ph_agua")),
        "mo": Coluna(("mo", "materia_organica", "om", "organic_matter")),
        "ctc": Coluna(("ctc", "cec", "ctc_ph7", "t")),
        "p": Coluna(("p", "p_mehlich", "fosforo", "phosphorus")),
        "k": Coluna(("k", "potassio", "potassium")),
        "ca": Coluna(("ca", "calcio", "calcium")),
        "mg": Coluna(("mg", "magnesio", "magnesium")),
        "s": Coluna(("s", "enxofre", "sulfur")),
        "b": Coluna(("b", "boro", "boron")),
        "zn": Coluna(("zn", "zinco", "zinc")),
        "mn": Coluna(("mn", "manganes", "manganese")),
        "cu": Coluna(("cu", "cobre", "copper")),
        "v_pct": Coluna(("v_pct", "v", "v_percent", "saturacao_bases", "base_saturation")),
    },
    TipoUpload.NDVI: {
        "talhao_id": _TALHAO,
        "data": Coluna(("data", "date", "image_date", "acquisition_date"), True, "data"),
        "ndvi_medio": Coluna(("ndvi_medio", "ndvi_mean", "ndvi_avg", "ndvi", "mean", "avg"), True),
        "ndvi_min": Coluna(("ndvi_min", "min")),
        "ndvi_max": Coluna(("ndvi_max", "max")),
    },
    TipoUpload.COLHEITA: {
        "talhao_id": _TALHAO,
        "data": Coluna(("data", "date", "data_colheita", "harvest_date"), True, "data"),
        "produtividade_kg_ha": Coluna(
            ("produtividade_kg_ha", "produtividade", "yield_kg_ha", "yield", "dry_yield_kg_ha", "rendimento"),
            True,
        ),
    },
}


def normalizar(nome: str) -> str:
    sem_unidade = re.sub(r"[\[\(].*?[\]\)]", " ", str(nome))
    sem_acento = unicodedata.normalize("NFKD", sem_unidade).encode("ascii", "ignore").decode()
    sem_acento = sem_acento.replace("%", " pct ")
    base = re.sub(r"[^a-z0-9]+", "_", sem_acento.lower()).strip("_")
    return "v_pct" if base == "v_pct" else base


def converter_numero(valor) -> float | None:
    if valor is None or (isinstance(valor, float) and pd.isna(valor)):
        return None
    texto = str(valor).strip()
    if texto == "" or texto.lower() in {"nan", "na", "-", "null"}:
        return None
    if "," in texto:
        texto = texto.replace(".", "").replace(",", ".") if "." in texto else texto.replace(",", ".")
    return float(texto)  # ValueError vira erro da linha


def converter_data(valor, com_hora: bool) -> datetime | date:
    if valor is None or str(valor).strip() == "":
        raise ValueError("data vazia")
    texto = str(valor).strip()
    iso = re.match(r"^\d{4}-\d{2}-\d{2}", texto) is not None
    ts = pd.to_datetime(texto, dayfirst=not iso, errors="coerce")
    if pd.isna(ts):
        raise ValueError(f"data inválida: {texto}")
    return ts.to_pydatetime().replace(tzinfo=None) if com_hora else ts.date()


def _ler_tabela(conteudo: bytes, nome_arquivo: str) -> pd.DataFrame:
    if nome_arquivo.lower().endswith((".xlsx", ".xls")):
        return pd.read_excel(io.BytesIO(conteudo), dtype=str)
    texto = conteudo.decode("utf-8-sig", errors="replace")
    return pd.read_csv(io.StringIO(texto), sep=None, engine="python", dtype=str, skip_blank_lines=True)


def _resolver_colunas(df: pd.DataFrame, mapa: dict[str, Coluna]) -> dict[str, tuple[str, float]]:
    """Canônico → (coluna original do DataFrame, fator)."""
    por_normalizado = {}
    for original in df.columns:
        por_normalizado.setdefault(normalizar(original), original)
    resolvidas = {}
    for canonico, col in mapa.items():
        for apelido in col.apelidos:
            if apelido in por_normalizado:
                resolvidas[canonico] = (por_normalizado[apelido], col.fator.get(apelido, 1.0))
                break
    return resolvidas


def _mapa_talhoes(db: Session) -> dict[str, int]:
    mapa = {}
    for t in db.scalars(select(Talhao)):
        mapa[str(t.id)] = t.id
        mapa[normalizar(t.nome)] = t.id
    return mapa


def _converter_linha(bruta: dict, mapa, resolvidas, talhoes) -> dict:
    linha = {}
    for canonico, (original, fator) in resolvidas.items():
        valor = bruta.get(original)
        tipo = mapa[canonico].tipo
        if canonico == "talhao_id":
            chave = str(valor).strip() if valor is not None else ""
            talhao_id = talhoes.get(chave) or talhoes.get(normalizar(chave))
            if talhao_id is None:
                raise ValueError(f"talhão não encontrado: {chave}")
            linha[canonico] = talhao_id
        elif tipo in ("data", "datahora"):
            linha[canonico] = converter_data(valor, com_hora=tipo == "datahora")
        elif tipo == "str":
            if valor is None or str(valor).strip() == "" or str(valor) == "nan":
                raise ValueError(f"{canonico} vazio")
            linha[canonico] = str(valor).strip()
        else:
            try:
                numero = converter_numero(valor)
            except ValueError:
                raise ValueError(f"{canonico}: valor inválido '{valor}'") from None
            if numero is None and mapa[canonico].obrigatoria:
                raise ValueError(f"{canonico} vazio")
            if numero is not None:
                numero *= fator
                numero = int(numero) if tipo == "int" else numero
            linha[canonico] = numero
    return linha


def ler_linhas(
    db: Session, tipo: TipoUpload, conteudo: bytes, nome_arquivo: str
) -> tuple[list[dict], list[dict]]:
    """Lê e valida o arquivo. Devolve (linhas válidas já convertidas, erros por linha)."""
    try:
        df = _ler_tabela(conteudo, nome_arquivo)
    except Exception as exc:  # arquivo ilegível
        raise HTTPException(400, f"Não foi possível ler o arquivo: {exc}") from None

    mapa = MAPAS[tipo]
    resolvidas = _resolver_colunas(df, mapa)
    faltando = [c for c, col in mapa.items() if col.obrigatoria and c not in resolvidas]
    if faltando:
        raise HTTPException(400, f"Colunas obrigatórias ausentes: {', '.join(faltando)}")

    talhoes = _mapa_talhoes(db) if "talhao_id" in mapa else {}
    validas, erros = [], []
    for i, bruta in enumerate(df.to_dict(orient="records")):
        numero_linha = i + 2  # linha 1 é o cabeçalho
        try:
            validas.append(_converter_linha(bruta, mapa, resolvidas, talhoes))
        except (ValueError, TypeError) as exc:
            erros.append({"linha": numero_linha, "erro": str(exc)})
    return validas, erros


def _gravar(db: Session, tipo: TipoUpload, linhas: list[dict]) -> None:
    if not linhas:
        return
    if tipo == TipoUpload.CLIMA:
        upsert(db, LeituraClima, _deduplicar(linhas, ("data_hora",)), ("data_hora",))
    elif tipo == TipoUpload.SOLO:
        upsert(
            db,
            LeituraSolo,
            _deduplicar(linhas, ("talhao_id", "ponto", "data_coleta")),
            ("talhao_id", "ponto", "data_coleta"),
        )
    elif tipo == TipoUpload.NDVI:
        upsert(db, MetricaTalhao, _deduplicar(linhas, ("talhao_id", "data")), ("talhao_id", "data"))
    elif tipo == TipoUpload.COLHEITA:
        # camada de colheita vem por ponto: agrega pela média por talhão e data
        grupos: dict[tuple, list[float]] = defaultdict(list)
        for linha in linhas:
            grupos[(linha["talhao_id"], linha["data"])].append(linha["produtividade_kg_ha"])
        agregadas = [
            {"talhao_id": t, "data": d, "produtividade_kg_ha": round(sum(v) / len(v), 1)}
            for (t, d), v in grupos.items()
        ]
        upsert(db, MetricaTalhao, agregadas, ("talhao_id", "data"))
    if tipo in (TipoUpload.CLIMA, TipoUpload.NDVI):
        atualizar_balanco_hidrico(db)


def _deduplicar(linhas: list[dict], chaves: tuple[str, ...]) -> list[dict]:
    """Mantém a última ocorrência de cada chave única dentro do próprio arquivo."""
    return list({tuple(linha[c] for c in chaves): linha for linha in linhas}.values())


def atualizar_balanco_hidrico(db: Session, janela_dias: int | None = None) -> None:
    """Balanço hídrico acumulado (chuva − ETP) nos N dias até cada data de métrica."""
    from app.core.config import settings
    from app.services.clima import balanco_hidrico

    janela = janela_dias or settings.regras["hidrico"]["janela_dias"]
    for metrica in db.scalars(select(MetricaTalhao)):
        valor = balanco_hidrico(db, metrica.data, janela)
        if valor is not None:
            metrica.balanco_hidrico_mm = valor
    db.commit()


def importar(
    db: Session, tipo: TipoUpload, conteudo: bytes, nome_arquivo: str, usuario_id: int | None
) -> dict:
    validas, erros = ler_linhas(db, tipo, conteudo, nome_arquivo)
    _gravar(db, tipo, validas)
    if usuario_id is not None:
        db.add(
            Upload(
                usuario_id=usuario_id,
                nome_arquivo=nome_arquivo,
                tipo=tipo,
                linhas_ok=len(validas),
                linhas_erro=len(erros),
                erros=erros,
            )
        )
        db.commit()
    return {"linhas_ok": len(validas), "linhas_erro": len(erros), "erros": erros}
