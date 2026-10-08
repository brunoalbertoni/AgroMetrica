"""Popula o banco com o dataset FarmLab (EKOS, Metos, OneSoil e Cropman).

Uso (dentro de backend/, com o venv ativo):
    python -m scripts.seed_farmlab                      # lê data/raw/farmlab
    python -m scripts.seed_farmlab --limpar             # apaga os dados agronômicos antes (mantém usuários)
    python -m scripts.seed_farmlab --sem-fotos          # não baixa as fotos das armadilhas
    python -m scripts.seed_farmlab --data-dir C:/dados/farmlab

Os arquivos são procurados em qualquer subpasta de --data-dir (ver README, "Dados do FarmLab").
O script é idempotente: rodar de novo atualiza em vez de duplicar.
"""

import argparse
import json
import logging
import re
import shutil
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from urllib.parse import urlparse

import cv2
import httpx
import numpy as np
import pandas as pd
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_senha
from app.models import (
    Alerta,
    Diagnostico,
    Imagem,
    LeituraClima,
    LeituraSolo,
    MetricaTalhao,
    OperacaoTalhao,
    Praga,
    Prescricao,
    Produto,
    Talhao,
    Upload,
    Usuario,
    praga_produto,
)
from app.models.enums import ClasseProduto, Finalidade, Perfil, Sistema, StatusImagem, TipoImagem, TipoUpload
from app.services import diagnostico, geo, ingestao, storage
from app.services.ingestao import converter_numero, normalizar
from app.services.upsert import upsert

log = logging.getLogger("seed")

RAIZ_REPO = Path(__file__).resolve().parents[2]
DATA_DIR_PADRAO = RAIZ_REPO / "data" / "raw" / "farmlab"

USUARIOS = [
    ("Administrador", "admin@agrometrica.com.br", "admin123", Perfil.ADMIN),
    ("Agrônomo Responsável", "agronomo@agrometrica.com.br", "agro123", Perfil.AGRONOMO),
]

# EKOS grava em UTC; Metos e o restante do sistema usam o horário local da fazenda (Marília-SP)
UTC_PARA_LOCAL = timedelta(hours=-3)
FOTO_LADO_MAX = 1600
PASTA_FOTOS = "farmlab/armadilhas"
PASTA_NDVI = "farmlab/ndvi"
# dias de uma operação com menos que esta fração da área total são sobras (manobra, borda)
FRACAO_MINIMA_DIA = 0.05


# ---------------------------------------------------------------- leitura


def _ler(caminho: Path) -> pd.DataFrame:
    if caminho.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(caminho, dtype=str)
    return pd.read_csv(caminho, sep=None, engine="python", dtype=str, encoding="utf-8-sig")


def _coluna(df: pd.DataFrame, *apelidos: str) -> str | None:
    normalizados = {normalizar(c): c for c in df.columns}
    return next((normalizados[a] for a in apelidos if a in normalizados), None)


def _achar(data_dir: Path, nome: str) -> Path | None:
    """Primeiro arquivo com esse nome (sem diferenciar maiúsculas), preferindo CSV a XLSX."""
    alvo = nome.lower()
    achados = [
        p
        for p in data_dir.rglob("*")
        if p.is_file() and p.stem.lower() == alvo and p.suffix.lower() in (".csv", ".xlsx", ".xls")
    ]
    return sorted(achados, key=lambda p: (p.suffix.lower() != ".csv", str(p)))[0] if achados else None


def _ler_imagem(caminho: Path) -> np.ndarray | None:
    """cv2.imread não abre caminhos com acento no Windows ("Satélite"); imdecode abre."""
    try:
        return cv2.imdecode(np.fromfile(caminho, dtype=np.uint8), cv2.IMREAD_COLOR)
    except OSError:
        return None


def _vazio(valor) -> bool:
    return valor is None or (isinstance(valor, float) and pd.isna(valor)) or str(valor).strip() in ("", "nan")


# ---------------------------------------------------------------- limpeza e usuários


def limpar_dados(db: Session) -> None:
    """Apaga os dados agronômicos (talhões, leituras, diagnósticos, catálogo). Usuários ficam."""
    for modelo in (Alerta, Prescricao, Diagnostico, Imagem, OperacaoTalhao, MetricaTalhao, LeituraSolo):
        db.execute(delete(modelo))
    db.execute(delete(praga_produto))
    for modelo in (Produto, Praga, LeituraClima, Upload, Talhao):
        db.execute(delete(modelo))
    db.commit()
    # pasta das imagens sintéticas da versão anterior do seed
    antiga = storage.raiz() / "armadilhas"
    if antiga.exists():
        shutil.rmtree(antiga)
    log.info("Dados agronômicos apagados")


def garantir_usuarios(db: Session) -> None:
    for nome, email, senha, perfil in USUARIOS:
        if db.scalar(select(Usuario).where(Usuario.email == email)) is None:
            db.add(Usuario(nome=nome, email=email, senha_hash=hash_senha(senha), perfil=perfil, ativo=True))
    db.commit()


# ---------------------------------------------------------------- talhões (EKOS fields.csv)


def _sistema(texto: str) -> Sistema:
    t = normalizar(texto)
    return (
        Sistema.AGRO_4_0
        if any(k in t for k in ("4_0", "digital", "smart", "precisao", "precision"))
        else Sistema.CONVENCIONAL
    )


def _finalidade(texto: str) -> Finalidade:
    t = normalizar(texto)
    return Finalidade.SILAGEM if any(k in t for k in ("silag", "silage")) else Finalidade.GRAO


def importar_talhoes(db: Session, arquivo: Path) -> dict[str, int]:
    """Cria/atualiza os talhões. Devolve idField do EKOS → id no banco.

    O EKOS põe a área no nome ("Grão 4.0 - 19,3 ha"); sem ela, calcula pelo polígono.
    """
    df = _ler(arquivo)
    c_id = _coluna(df, "idfield", "field_id", "id")
    c_nome = _coluna(df, "fieldname", "field_name", "name", "nome")
    c_geo = _coluna(df, "fieldgeom", "geometry", "geometria", "wkt")
    if c_nome is None:
        raise SystemExit(f"{arquivo.name}: coluna de nome do talhão não encontrada ({list(df.columns)})")
    codigos = {}
    for linha in df.to_dict(orient="records"):
        rotulo = str(linha[c_nome]).strip()
        area_no_nome = re.search(r"\s*-\s*([\d.,]+)\s*ha\s*$", rotulo, re.IGNORECASE)
        nome = rotulo[: area_no_nome.start()].strip() if area_no_nome else rotulo
        geometria = geo.para_polygon(linha[c_geo]) if c_geo and not _vazio(linha[c_geo]) else None
        area = converter_numero(area_no_nome.group(1)) if area_no_nome else geo.area_ha(geometria)
        codigo = str(linha[c_id]).strip() if c_id else None

        t = None
        if codigo:
            t = db.scalar(select(Talhao).where(Talhao.codigo_externo == codigo))
        t = t or db.scalar(select(Talhao).where(Talhao.nome == nome)) or Talhao(nome=nome)
        t.nome, t.codigo_externo, t.cultura = nome, codigo, "Milho"
        t.area_ha = round(area or 0, 2)
        t.sistema, t.finalidade = _sistema(nome), _finalidade(nome)
        t.geometria = geometria or t.geometria
        db.add(t)
        db.commit()
        if codigo:
            codigos[codigo] = t.id
    log.info("Talhões: %d", len(codigos))
    return codigos


# ---------------------------------------------------------------- pragas (EKOS pest_details.csv)


@dataclass
class Pragas:
    por_nome: dict[str, Praga]  # nome popular normalizado → praga
    por_deteccao: dict[str, Praga]  # nome que o modelo de detecção usa ("Spodoptera spp.") → praga

    def achar(self, nome: str | None) -> Praga | None:
        chave = normalizar(nome or "")
        return self.por_deteccao.get(chave) or self.por_nome.get(chave)


def importar_pragas(db: Session, arquivo: Path, cultura: str = "Milho") -> Pragas:
    df = _ler(arquivo)
    c_nome = _coluna(df, "namepopular", "pest_name", "nome", "name")
    c_cient = _coluna(df, "namescientific", "scientific_name", "nome_cientifico")
    c_cultura = _coluna(df, "culture", "crop", "cultura")
    c_deteccao = _coluna(df, "detectionname", "detection_name")
    c_alerta, c_controle, c_dano = (_coluna(df, n) for n in ("alert", "control", "damage"))
    if not all((c_nome, c_alerta, c_controle, c_dano)):
        raise SystemExit(f"{arquivo.name}: colunas de nome/limiares não encontradas ({list(df.columns)})")
    if c_cultura:
        df = df[df[c_cultura].map(normalizar) == normalizar(cultura)]

    por_nome, por_deteccao = {}, {}
    for linha in df.to_dict(orient="records"):
        nome = str(linha[c_nome]).strip()
        if normalizar(nome) in por_nome:  # o arquivo repete as pragas
            continue
        p = db.scalar(select(Praga).where(Praga.nome == nome)) or Praga(nome=nome)
        p.nome_cientifico = None if not c_cient or _vazio(linha[c_cient]) else str(linha[c_cient]).strip()
        p.cultura = cultura
        p.limiar_alerta = converter_numero(linha[c_alerta])
        p.limiar_controle = converter_numero(linha[c_controle])
        p.limiar_dano = converter_numero(linha[c_dano])
        db.add(p)
        db.commit()
        por_nome[normalizar(nome)] = p
        deteccao = linha[c_deteccao] if c_deteccao else None
        if not _vazio(deteccao) and normalizar(deteccao) != "sa":  # "sa" = sem detecção automática
            por_deteccao[normalizar(deteccao)] = p
    log.info("Pragas de %s: %d", cultura, len(por_nome))
    return Pragas(por_nome, por_deteccao)


# ---------------------------------------------------------------- clima (Metos)


def importar_clima(db: Session, data_dir: Path) -> None:
    arquivos = sorted(p for p in data_dir.rglob("*.csv") if "metos" in str(p.relative_to(data_dir)).lower())
    if not arquivos:
        log.warning("Nenhum arquivo do Metos encontrado")
    for arquivo in arquivos:
        r = ingestao.importar(db, TipoUpload.CLIMA, arquivo.read_bytes(), arquivo.name, None)
        log.info("Clima %s: %d leituras, %d com erro", arquivo.name, r["linhas_ok"], r["linhas_erro"])


# ---------------------------------------------------------------- NDVI (OneSoil)


def importar_ndvi(db: Session, arquivo: Path, data_dir: Path, localizador: geo.Localizador) -> None:
    """ndvi_metadata.csv: uma linha por imagem; o talhão sai do centro da imagem (EPSG:3857).

    Datas sem valor (nuvem) ficam de fora. A imagem colorida (JPG) vira uma Imagem NDVI do talhão.
    """
    df = _ler(arquivo)
    jpgs = {p.stem: p for p in data_dir.rglob("*.jpg")}
    talhao_da_safra: dict[str, int | None] = {}
    metricas, sem_talhao = [], set()
    for linha in df.to_dict(orient="records"):
        safra = linha["season_id"]
        if safra not in talhao_da_safra:
            x = (float(linha["bounds_left"]) + float(linha["bounds_right"])) / 2
            y = (float(linha["bounds_bottom"]) + float(linha["bounds_top"])) / 2
            if str(linha.get("crs", "")).upper() == "EPSG:4326":
                lon, lat = x, y
            else:
                lon, lat = geo.mercator_para_lonlat(x, y)
            talhao_da_safra[safra] = localizador.talhao(lon, lat)
        talhao_id = talhao_da_safra[safra]
        if talhao_id is None:
            sem_talhao.add(safra)
            continue
        media = converter_numero(linha.get("b1_mean"))
        achada = re.search(r"(\d{4}-\d{2}-\d{2})", linha["filename"])
        if media is None or achada is None:
            continue
        dia = date.fromisoformat(achada.group(1))
        metricas.append(
            {
                "talhao_id": talhao_id,
                "data": dia,
                "ndvi_medio": round(media, 4),
                "ndvi_min": converter_numero(linha.get("b1_min")),
                "ndvi_max": converter_numero(linha.get("b1_max")),
            }
        )
        jpg = jpgs.get(Path(linha["filename"]).stem)
        if jpg is not None:
            _registrar_imagem_ndvi(db, talhao_id, jpg, dia)
    upsert(db, MetricaTalhao, metricas, ("talhao_id", "data"))
    for safra in sem_talhao:
        log.warning("NDVI: a área da safra %s não cai em nenhum talhão", safra)
    log.info("NDVI: %d leituras", len(metricas))


def _registrar_imagem_ndvi(db: Session, talhao_id: int, origem: Path, dia: date) -> None:
    caminho = f"{PASTA_NDVI}/{origem.name}"
    destino = storage.caminho_absoluto(caminho)
    if not destino.exists():
        destino.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(origem, destino)
    if db.scalar(select(Imagem).where(Imagem.caminho == caminho)) is None:
        db.add(
            Imagem(
                talhao_id=talhao_id,
                tipo=TipoImagem.NDVI_GEOTIFF,
                caminho=caminho,
                data_captura=datetime.combine(dia, datetime.min.time()),
                status=StatusImagem.PROCESSADO,
            )
        )
        db.commit()


# ---------------------------------------------------------------- operações de máquina (EKOS)


def _nome_operacao(bruto, camada: str) -> str | None:
    t = normalizar(bruto) if not _vazio(bruto) else ""
    if "calagem" in t:
        return "Calagem"
    if "gessagem" in t:
        return "Gessagem"
    if "plantio" in t:
        return "Plantio" if camada == "plantio" else "Adubação de plantio"
    return None  # sem rótulo ou fora do manejo do talhão (ex.: medição de área)


def _trechos(arquivo: Path, localizador: geo.Localizador, camada: str, valores: dict[str, tuple[str, ...]]):
    """Lê uma camada de máquina e devolve (talhão, operação, dia, área, {campo: valor}) por trecho."""
    df = _ler(arquivo)
    c_geo = _coluna(df, "geometry")
    c_data = _coluna(df, "date_time", "datetime")
    c_op = _coluna(df, "operation")
    c_area = _coluna(df, "area_ha", "area")
    colunas = {campo: _coluna(df, *apelidos) for campo, apelidos in valores.items()}
    for linha in df[[c for c in (c_geo, c_data, c_op, c_area, *colunas.values()) if c]].itertuples(
        index=False
    ):
        registro = dict(
            zip([c for c in (c_geo, c_data, c_op, c_area, *colunas.values()) if c], linha, strict=True)
        )
        operacao = _nome_operacao(registro.get(c_op), camada)
        ponto = geo.centro(registro[c_geo]) if operacao else None
        talhao_id = localizador.talhao(*ponto) if ponto else None
        area = converter_numero(registro.get(c_area)) or 0
        if talhao_id is None or area <= 0:
            continue
        dia = ingestao.converter_data(str(registro[c_data])[:10], com_hora=False)
        yield (
            talhao_id,
            operacao,
            dia,
            area,
            {k: converter_numero(registro[c]) for k, c in colunas.items() if c},
        )


def importar_operacoes(db: Session, data_dir: Path, localizador: geo.Localizador) -> list[dict]:
    """Calagem, gessagem e adubação (LAYER_MAP_FERTILIZATION) e plantio (LAYER_MAP_PLANTING),
    agregados por talhão com média de dose ponderada pela área."""
    camadas = [
        (
            "LAYER_MAP_FERTILIZATION",
            "adubacao",
            "kg/ha",
            {"aplicada": ("applieddos_kg_ha",), "configurada": ("configured_kg_ha",)},
        ),
        ("LAYER_MAP_PLANTING", "plantio", "plantas/ha", {"aplicada": ("population_ha",)}),
    ]
    grupos: dict[tuple[int, str], dict] = {}
    for nome, camada, unidade, valores in camadas:
        arquivo = _achar(data_dir, nome)
        if arquivo is None:
            log.warning("%s não encontrado", nome)
            continue
        for talhao_id, operacao, dia, area, v in _trechos(arquivo, localizador, camada, valores):
            g = grupos.setdefault(
                (talhao_id, operacao),
                {
                    "unidade": unidade,
                    "dias": defaultdict(float),
                    "soma": defaultdict(float),
                    "peso": defaultdict(float),
                },
            )
            g["dias"][dia] += area
            for campo, valor in v.items():
                if valor is not None and valor > 0:
                    g["soma"][campo] += valor * area
                    g["peso"][campo] += area

    linhas = []
    for (talhao_id, operacao), g in grupos.items():
        total = sum(g["dias"].values())
        dias = sorted(d for d, a in g["dias"].items() if a >= FRACAO_MINIMA_DIA * total) or sorted(g["dias"])
        media = {
            c: round(g["soma"][c] / g["peso"][c], 1) if g["peso"][c] else None
            for c in ("aplicada", "configurada")
        }
        linhas.append(
            {
                "talhao_id": talhao_id,
                "operacao": operacao,
                "data_inicio": dias[0],
                "data_fim": dias[-1],
                "area_ha": round(total, 2),
                "dose_aplicada": media["aplicada"],
                "dose_configurada": media["configurada"],
                "unidade": g["unidade"],
            }
        )
    upsert(db, OperacaoTalhao, linhas, ("talhao_id", "operacao"))
    for linha in linhas:
        if linha["operacao"] == "Plantio":
            db.get(Talhao, linha["talhao_id"]).data_plantio = linha["data_inicio"]
    db.commit()
    log.info("Operações por talhão: %d", len(linhas))
    return linhas


def importar_colheita(db: Session, arquivo: Path, localizador: geo.Localizador) -> None:
    """LAYER_MAP_GRAIN_HARVESTING: produtividade média (ponderada pela área) dos trechos de colheita
    que caem dentro de cada talhão. Trechos de outras operações ou fora dos talhões são ignorados."""
    df = _ler(arquivo)
    c_geo, c_data, c_op = _coluna(df, "geometry"), _coluna(df, "date_time"), _coluna(df, "operation")
    c_area, c_prod = _coluna(df, "area_ha"), _coluna(df, "yield_kg_ha", "yield")
    soma, peso, ultimo = defaultdict(float), defaultdict(float), {}
    for linha in df[[c_geo, c_data, c_op, c_area, c_prod]].itertuples(index=False):
        wkt, quando, operacao, area, produtividade = linha
        if "colheita" not in normalizar(operacao or "") and "harvest" not in normalizar(operacao or ""):
            continue
        area, produtividade = converter_numero(area) or 0, converter_numero(produtividade) or 0
        ponto = geo.centro(wkt)
        talhao_id = localizador.talhao(*ponto) if ponto else None
        if talhao_id is None or area <= 0 or produtividade <= 0:
            continue
        soma[talhao_id] += produtividade * area
        peso[talhao_id] += area
        dia = ingestao.converter_data(str(quando)[:10], com_hora=False)
        ultimo[talhao_id] = max(dia, ultimo.get(talhao_id, dia))
    linhas = [
        {"talhao_id": t, "data": ultimo[t], "produtividade_kg_ha": round(soma[t] / peso[t], 1)} for t in soma
    ]
    upsert(db, MetricaTalhao, linhas, ("talhao_id", "data"))
    if not linhas:
        log.warning("Colheita: nenhum trecho de colheita dentro dos talhões cadastrados")
    log.info("Colheita: %d talhões com produtividade", len(linhas))


# ---------------------------------------------------------------- catálogo (EKOS agricultural_inputs.csv)


def importar_insumos(db: Session, arquivo: Path, operacoes: list[dict]) -> None:
    """Insumos cadastrados no EKOS. A faixa de dose vem do que as máquinas aplicaram nos talhões:
    calcário → calagem, gesso → gessagem, semente → população do plantio."""
    df = _ler(arquivo)
    c_nome = _coluna(df, "agricultural_input_name", "name", "nome")
    c_marca = _coluna(df, "agricultural_input_brand", "brand", "marca")
    c_classe = _coluna(df, "agricultural_input_class", "class", "classe")

    def faixa(operacao: str, campo: str) -> tuple[float, float] | None:
        valores = [o[campo] for o in operacoes if o["operacao"] == operacao and o[campo]]
        return (min(valores), max(valores)) if valores else None

    total = 0
    for linha in df.to_dict(orient="records"):
        nome = str(linha[c_nome]).strip()
        marca = "" if not c_marca or _vazio(linha[c_marca]) else str(linha[c_marca]).strip()
        classe_origem = "" if not c_classe or _vazio(linha[c_classe]) else str(linha[c_classe]).strip()
        n, c = normalizar(nome), normalizar(classe_origem)
        if "semente" in c:
            classe, dose, unidade = ClasseProduto.SEMENTE, faixa("Plantio", "dose_aplicada"), "plantas/ha"
        elif "calcario" in n:
            classe, dose, unidade = ClasseProduto.CORRETIVO, faixa("Calagem", "dose_configurada"), "kg/ha"
        elif "gesso" in n:
            classe, dose, unidade = ClasseProduto.CORRETIVO, faixa("Gessagem", "dose_configurada"), "kg/ha"
        else:
            log.warning("Insumo %s: sem operação correspondente para estimar a dose; ignorado", nome)
            continue
        if dose is None:
            log.warning("Insumo %s: nenhuma aplicação nos talhões para estimar a dose; ignorado", nome)
            continue
        nome_comercial = f"{nome} {marca}".strip()
        p = db.scalar(select(Produto).where(Produto.nome_comercial == nome_comercial)) or Produto(
            nome_comercial=nome_comercial
        )
        p.classe, p.unidade, p.carencia_dias = classe, unidade, None
        p.ingrediente_ativo = None if classe == ClasseProduto.SEMENTE else classe_origem or None
        p.dose_min, p.dose_max = round(dose[0]), round(dose[1])
        db.add(p)
        total += 1
    db.commit()
    log.info("Insumos no catálogo: %d", total)


# ---------------------------------------------------------------- solo (Cropman)

# Cropman (laboratório IAC): Ca, Mg, K, CTC e SB em mmolc/dm³; o sistema usa cmolc/dm³
_SOLO = {
    "ph": ("PHCACL2", 1),
    "mo": ("MO", 1),
    "ctc": ("CTC", 0.1),
    "p": ("P", 1),
    "k": ("K", 0.1),
    "ca": ("CA", 0.1),
    "mg": ("MG", 0.1),
    "s": ("S", 1),
    "b": ("B", 1),
    "zn": ("ZN", 1),
    "mn": ("MN", 1),
    "cu": ("CU", 1),
    "v_pct": ("SATB", 1),
}
_PROFUNDIDADES = (("", "0–20 cm"), ("_2", "20–40 cm"))


def importar_solo(db: Session, arquivo: Path, data_dir: Path, codigos: dict[str, int]) -> None:
    """A análise do Cropman não diz de que talhão é cada amostra: isso vem de amostras_solo.csv
    (colunas amostra;talhao;data_coleta, com o talhão pelo nome ou pelo idField do EKOS)."""
    vinculo = _achar(data_dir, "amostras_solo")
    if vinculo is None:
        log.warning(
            "Solo: %s não tem o talhão de cada amostra. Crie amostras_solo.csv (amostra;talhao;data_coleta) "
            "em %s para importar a análise",
            arquivo.name,
            data_dir,
        )
        return
    talhoes = {normalizar(t.nome): t.id for t in db.scalars(select(Talhao))}
    talhoes.update({normalizar(k): v for k, v in codigos.items()})
    amostras = {}
    for linha in _ler(vinculo).to_dict(orient="records"):
        chave = {normalizar(k): v for k, v in linha.items()}
        talhao_id = talhoes.get(normalizar(chave.get("talhao", "")))
        if talhao_id is None:
            log.warning("amostras_solo: talhão não encontrado: %s", chave.get("talhao"))
            continue
        amostras[str(chave["amostra"]).strip()] = (
            talhao_id,
            ingestao.converter_data(chave["data_coleta"], com_hora=False),
        )

    df = _ler(arquivo)
    linhas = []
    for bruta in df.to_dict(orient="records"):
        linha = {str(k).strip().upper(): v for k, v in bruta.items()}
        amostra = str(linha.get("AMOSTRA", "")).strip()
        if amostra not in amostras:
            continue
        talhao_id, coleta = amostras[amostra]
        for sufixo, rotulo in _PROFUNDIDADES:
            valores = {}
            for campo, (coluna, fator) in _SOLO.items():
                v = converter_numero(linha.get(coluna + sufixo))
                valores[campo] = round(v * fator, 3) if v is not None else None
            if all(v is None for v in valores.values()):
                continue
            linhas.append(
                {"talhao_id": talhao_id, "ponto": f"{amostra} ({rotulo})", "data_coleta": coleta, **valores}
            )
    upsert(db, LeituraSolo, linhas, ("talhao_id", "ponto", "data_coleta"))
    log.info("Solo: %d leituras (amostras × profundidades)", len(linhas))


# ---------------------------------------------------------------- armadilhas (EKOS)


def _dimensoes_cache() -> tuple[Path, dict]:
    arquivo = storage.raiz() / PASTA_FOTOS / "_dimensoes.json"
    return arquivo, (json.loads(arquivo.read_text()) if arquivo.exists() else {})


def baixar_fotos(urls: set[str]) -> dict[str, tuple[str, int, int]]:
    """Baixa as fotos das armadilhas (S3 do EKOS), reduz para até 1600 px e guarda no storage.

    Devolve url → (caminho relativo, largura original, altura original). As caixas de detecção
    vêm em pixels da foto original, por isso as dimensões originais ficam registradas.
    Fotos já baixadas não são baixadas de novo.
    """
    arquivo_dim, dimensoes = _dimensoes_cache()
    pasta = storage.raiz() / PASTA_FOTOS
    pasta.mkdir(parents=True, exist_ok=True)

    def uma(cliente: httpx.Client, url: str):
        nome = Path(urlparse(url).path).name
        caminho = f"{PASTA_FOTOS}/{nome}"
        if nome in dimensoes and (pasta / nome).exists():
            return url, (caminho, *dimensoes[nome])
        try:
            resposta = cliente.get(url)
            resposta.raise_for_status()
        except httpx.HTTPError as exc:
            log.warning("Foto não baixada (%s): %s", url, exc)
            return url, None
        img = cv2.imdecode(np.frombuffer(resposta.content, np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            log.warning("Foto ilegível: %s", url)
            return url, None
        altura, largura = img.shape[:2]
        escala = FOTO_LADO_MAX / max(altura, largura)
        if escala < 1:
            img = cv2.resize(
                img, (round(largura * escala), round(altura * escala)), interpolation=cv2.INTER_AREA
            )
        (pasta / nome).write_bytes(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])[1].tobytes())
        return url, (caminho, largura, altura)

    resultado = {}
    pendentes = [u for u in urls if Path(urlparse(u).path).name not in dimensoes]
    if pendentes:
        log.info("Baixando %d fotos de armadilha (as já baixadas são reaproveitadas)", len(pendentes))
    with httpx.Client(timeout=60, follow_redirects=True) as cliente, ThreadPoolExecutor(8) as pool:
        for url, info in pool.map(lambda u: uma(cliente, u), sorted(urls)):
            if info is not None:
                resultado[url] = info
                dimensoes[Path(info[0]).name] = [info[1], info[2]]
    arquivo_dim.write_text(json.dumps(dimensoes))
    return resultado


def _deteccao(texto) -> tuple[dict[str, float], list[dict]]:
    """Coluna detection: ["1 Helicoverpa spp., 35 Spodoptera spp., ", "[{xmin, ymin, xmax, ymax,
    confidence, name}, ...]"] — resumo das contagens e as caixas em pixels da foto original."""
    if _vazio(texto):
        return {}, []
    partes = json.loads(texto)
    resumo = partes[0] if partes else ""
    caixas = json.loads(partes[1]) if len(partes) > 1 and partes[1] else []
    contagens = {nome.strip(): float(n) for n, nome in re.findall(r"(\d+)\s+([^,]+?)\s*,", resumo)}
    if not contagens:
        for c in caixas:
            contagens[c["name"]] = contagens.get(c["name"], 0) + 1
    return contagens, caixas


def importar_armadilhas(
    db: Session, data_dir: Path, pragas: Pragas, localizador: geo.Localizador, fotos: bool
) -> None:
    """traps_events.csv (eventos IMAGE) → diagnóstico de praga por foto e praga.

    O talhão vem da posição da armadilha (traps_list.csv); a contagem por praga, do resumo da detecção
    automática. Foto sem detecção conta tudo para a praga-alvo da armadilha (traps_data.csv).
    """
    arq_eventos, arq_lista = _achar(data_dir, "traps_events"), _achar(data_dir, "traps_list")
    if arq_eventos is None or arq_lista is None:
        log.warning("Armadilhas: traps_events e traps_list são necessários")
        return
    posicoes: dict[str, int | None] = {}
    for linha in _ler(arq_lista).to_dict(orient="records"):
        talhao_id = localizador.talhao(float(linha["longitude"]), float(linha["latitude"]))
        posicoes[str(linha["id"]).strip()] = talhao_id
        posicoes.setdefault(str(linha["code"]).strip(), talhao_id)
    alvo: dict[str, str] = {}
    arq_dados = _achar(data_dir, "traps_data")
    if arq_dados is not None:
        for linha in _ler(arq_dados).to_dict(orient="records"):
            for chave in ("trapId", "trapCode"):
                if not _vazio(linha.get(chave)) and not _vazio(linha.get("primaryPest")):
                    alvo.setdefault(str(linha[chave]).strip(), linha["primaryPest"])

    eventos = _ler(arq_eventos)
    eventos = eventos[eventos["type"] == "IMAGE"]
    baixadas = baixar_fotos({u for u in eventos["data"] if str(u).startswith("http")}) if fotos else {}

    total, sem_talhao = 0, 0
    for ev in eventos.to_dict(orient="records"):
        armadilha, codigo = str(ev["trapId"]).strip(), str(ev["code"]).strip()
        talhao_id = posicoes.get(armadilha) or posicoes.get(codigo)
        if talhao_id is None:
            sem_talhao += 1
            continue
        quando = ingestao.converter_data(ev["createdAt"], com_hora=True) + UTC_PARA_LOCAL
        contagens, caixas = _deteccao(ev["detection"])
        if not contagens and (converter_numero(ev["pestCount"]) or 0) > 0:
            contagens = {alvo.get(armadilha) or alvo.get(codigo): converter_numero(ev["pestCount"])}
        foto = baixadas.get(ev["data"])
        for nome, contagem in contagens.items():
            praga = pragas.achar(nome)
            if praga is None:
                log.warning("Armadilhas: praga desconhecida %r", nome)
                continue
            minhas = [c for c in caixas if pragas.achar(c["name"]) is praga]
            bboxes = []
            if foto is not None:
                _, largura, altura = foto
                bboxes = [
                    {
                        "x": round(c["xmin"] / largura, 4),
                        "y": round(c["ymin"] / altura, 4),
                        "w": round((c["xmax"] - c["xmin"]) / largura, 4),
                        "h": round((c["ymax"] - c["ymin"]) / altura, 4),
                        "rotulo": praga.nome,
                        "confianca": round(c["confidence"], 2),
                    }
                    for c in minhas
                ]
            confianca = round(sum(c["confidence"] for c in minhas) / len(minhas), 2) if minhas else None
            registrar_armadilha(
                db, talhao_id, praga, quando, contagem, bboxes, foto[0] if foto else None, confianca
            )
            total += 1
    if sem_talhao:
        log.warning("Armadilhas: %d fotos de armadilhas fora dos talhões", sem_talhao)
    log.info("Armadilhas: %d leituras (foto × praga)", total)


def registrar_armadilha(
    db: Session,
    talhao_id: int,
    praga: Praga,
    quando: datetime,
    contagem: float,
    bboxes: list[dict],
    caminho_imagem: str | None,
    confianca: float | None = None,
) -> None:
    imagem_id = None
    if caminho_imagem:
        img = db.scalar(select(Imagem).where(Imagem.caminho == caminho_imagem))
        if img is None:
            img = Imagem(
                talhao_id=talhao_id,
                tipo=TipoImagem.ARMADILHA,
                caminho=caminho_imagem,
                data_captura=quando,
                status=StatusImagem.PROCESSADO,
            )
            db.add(img)
            db.commit()
        imagem_id = img.id
    diagnostico.registrar_armadilha(
        db, talhao_id, praga.id, contagem, quando, imagem_id=imagem_id, bboxes=bboxes, confianca=confianca
    )


# ---------------------------------------------------------------- orquestração


def executar(db: Session, data_dir: Path, limpar: bool = False, fotos: bool = True) -> None:
    if not data_dir.exists():
        raise SystemExit(f"{data_dir} não existe. Coloque ali os arquivos do FarmLab (ver README).")
    if limpar:
        limpar_dados(db)
    garantir_usuarios(db)
    log.info("Importando FarmLab de %s", data_dir)

    fields = _achar(data_dir, "fields")
    if fields is None:
        raise SystemExit(f"fields.csv não encontrado em {data_dir}")
    codigos = importar_talhoes(db, fields)
    localizador = geo.Localizador({t.id: t.geometria for t in db.scalars(select(Talhao))})

    arquivo = _achar(data_dir, "pest_details")
    pragas = importar_pragas(db, arquivo) if arquivo else Pragas({}, {})
    importar_clima(db, data_dir)
    if arquivo := _achar(data_dir, "ndvi_metadata"):
        importar_ndvi(db, arquivo, data_dir, localizador)
    operacoes = importar_operacoes(db, data_dir, localizador)
    if arquivo := _achar(data_dir, "LAYER_MAP_GRAIN_HARVESTING"):
        importar_colheita(db, arquivo, localizador)
    if arquivo := _achar(data_dir, "agricultural_inputs"):
        importar_insumos(db, arquivo, operacoes)
    if arquivo := _achar(data_dir, "soil_analysis"):
        importar_solo(db, arquivo, data_dir, codigos)
    importar_armadilhas(db, data_dir, pragas, localizador, fotos)

    ingestao.atualizar_balanco_hidrico(db)
    for t in db.scalars(select(Talhao)).all():
        diagnostico.rodar(db, t.id)
    log.info("Pronto")


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    parser = argparse.ArgumentParser(description="Popula o AgroMétrica com o dataset FarmLab")
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR_PADRAO)
    parser.add_argument("--limpar", action="store_true", help="apaga os dados agronômicos antes de importar")
    parser.add_argument("--sem-fotos", action="store_true", help="não baixa as fotos das armadilhas")
    args = parser.parse_args()
    with SessionLocal() as db:
        executar(db, args.data_dir, limpar=args.limpar, fotos=not args.sem_fotos)


if __name__ == "__main__":
    sys.exit(main())
