"""Popula o banco com o dataset FarmLab (ou com dados de demonstração).

Uso (dentro de backend/, com o venv ativo):
    python -m scripts.seed_farmlab                      # usa data/raw/farmlab se existir, senão demo
    python -m scripts.seed_farmlab --data-dir C:/dados/farmlab
    python -m scripts.seed_farmlab --demo               # força os dados sintéticos

Arquivos esperados em --data-dir (nomes de coluna são reconhecidos por apelidos, ver ingestao.MAPAS):
    fields.csv            talhões (nome, área, sistema, finalidade, geometria WKT)
    pest_details.csv      pragas e limiares
    *metos*.csv|xlsx      clima horário da estação Metos
    *cropman*.csv|xlsx    análises de solo
    ndvi_metadata.csv     NDVI por talhão e data (OneSoil)
    *ekos*.csv|xlsx       camada de colheita (agregada por talhão)
    traps_events.csv      eventos das armadilhas com bounding boxes (+ imagens)

O script é idempotente: rodar de novo atualiza em vez de duplicar.
"""

import argparse
import json
import logging
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import cv2
import pandas as pd
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.security import hash_senha
from app.models import Imagem, LeituraClima, LeituraSolo, MetricaTalhao, Praga, Produto, Talhao, Usuario
from app.models.enums import Perfil, StatusImagem, TipoImagem, TipoUpload
from app.services import diagnostico, ingestao, storage
from app.services.ingestao import normalizar
from app.services.upsert import upsert
from scripts import demo_farmlab as demo

log = logging.getLogger("seed")

RAIZ_REPO = Path(__file__).resolve().parents[2]
DATA_DIR_PADRAO = RAIZ_REPO / "data" / "raw" / "farmlab"

USUARIOS = [
    ("Administrador", "admin@agrometrica.com.br", "admin123", Perfil.ADMIN),
    ("Agrônomo Responsável", "agronomo@agrometrica.com.br", "agro123", Perfil.AGRONOMO),
]


# ---------------------------------------------------------------- helpers comuns


def garantir_usuarios(db: Session) -> None:
    for nome, email, senha, perfil in USUARIOS:
        if db.scalar(select(Usuario).where(Usuario.email == email)) is None:
            db.add(Usuario(nome=nome, email=email, senha_hash=hash_senha(senha), perfil=perfil, ativo=True))
    db.commit()


def garantir_talhao(db: Session, nome, area_ha, cultura, sistema, finalidade, geometria) -> Talhao:
    t = db.scalar(select(Talhao).where(Talhao.nome == nome)) or Talhao(nome=nome)
    t.area_ha, t.cultura, t.sistema, t.finalidade = area_ha, cultura, sistema, finalidade
    t.geometria = geometria or t.geometria
    db.add(t)
    db.commit()
    return t


def garantir_praga(db: Session, nome, cientifico, cultura, alerta, controle, dano) -> Praga:
    p = db.scalar(select(Praga).where(Praga.nome == nome)) or Praga(nome=nome)
    p.nome_cientifico, p.cultura = cientifico, cultura
    p.limiar_alerta, p.limiar_controle, p.limiar_dano = alerta, controle, dano
    db.add(p)
    db.commit()
    return p


def garantir_produtos(db: Session) -> None:
    pragas = {p.nome: p for p in db.scalars(select(Praga))}
    for nome, ativo, classe, dmin, dmax, unidade, carencia, alvos in demo.PRODUTOS:
        p = db.scalar(select(Produto).where(Produto.nome_comercial == nome)) or Produto(nome_comercial=nome)
        p.ingrediente_ativo, p.classe, p.dose_min, p.dose_max = ativo, classe, dmin, dmax
        p.unidade, p.carencia_dias = unidade, carencia
        p.pragas = [pragas[a] for a in alvos if a in pragas]
        db.add(p)
    db.commit()


def registrar_armadilha(
    db: Session,
    talhao_id: int,
    praga: Praga,
    quando: datetime,
    contagem: float,
    bboxes: list[dict],
    caminho_imagem: str | None,
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
        db, talhao_id, praga.id, contagem, quando, imagem_id=imagem_id, bboxes=bboxes
    )


def finalizar(db: Session) -> None:
    ingestao.atualizar_balanco_hidrico(db)
    for t in db.scalars(select(Talhao)).all():
        diagnostico.rodar(db, t.id)


# ---------------------------------------------------------------- modo demonstração


def seed_demo(db: Session) -> None:
    log.info("Gerando dados de demonstração (sintéticos)")
    talhoes = []
    for i, (nome, sistema, finalidade, area, *_rest) in enumerate(demo.TALHOES):
        talhoes.append(garantir_talhao(db, nome, area, "Milho", sistema, finalidade, demo.geometria(i)))
    pragas = {n: garantir_praga(db, n, c, "Milho", a, co, d) for n, c, a, co, d in demo.PRAGAS}
    garantir_produtos(db)

    upsert(db, LeituraClima, demo.clima(), ("data_hora",))
    for i, t in enumerate(talhoes):
        upsert(db, MetricaTalhao, [{"talhao_id": t.id, **m} for m in demo.ndvi(i)], ("talhao_id", "data"))
        upsert(
            db,
            LeituraSolo,
            [{"talhao_id": t.id, **s} for s in demo.solo(i)],
            ("talhao_id", "ponto", "data_coleta"),
        )
        _, _, _, _, _, produtividade, colheita = demo.TALHOES[i]
        upsert(
            db,
            MetricaTalhao,
            [{"talhao_id": t.id, "data": colheita, "produtividade_kg_ha": produtividade}],
            ("talhao_id", "data"),
        )

    for i, t in enumerate(talhoes):
        for n, ev in enumerate(demo.armadilhas(i)):
            caminho, caixas = None, []
            if ev["foto"] and ev["contagem"] > 0:
                imagem, caixas = demo.imagem_armadilha(ev["contagem"], semente=1000 * i + n)
                caminho = f"armadilhas/demo_t{i + 1}_{ev['data']:%Y%m%d}.png"
                destino = storage.caminho_absoluto(caminho)
                destino.parent.mkdir(parents=True, exist_ok=True)
                cv2.imwrite(str(destino), imagem)
            registrar_armadilha(db, t.id, pragas[ev["praga"]], ev["data"], ev["contagem"], caixas, caminho)
    finalizar(db)


# ---------------------------------------------------------------- modo arquivos reais


def _ler(caminho: Path) -> pd.DataFrame:
    if caminho.suffix.lower() in (".xlsx", ".xls"):
        return pd.read_excel(caminho, dtype=str)
    return pd.read_csv(caminho, sep=None, engine="python", dtype=str, encoding="utf-8-sig")


def _coluna(df: pd.DataFrame, *apelidos: str) -> str | None:
    normalizados = {normalizar(c): c for c in df.columns}
    return next((normalizados[a] for a in apelidos if a in normalizados), None)


def _achar(data_dir: Path, *padroes: str) -> list[Path]:
    achados = []
    for padrao in padroes:
        achados += [p for p in data_dir.rglob(padrao) if p.suffix.lower() in (".csv", ".xlsx", ".xls")]
    return sorted(set(achados))


def _sistema(texto: str) -> str:
    t = normalizar(texto)
    return (
        "AGRO_4_0"
        if any(k in t for k in ("4_0", "40", "digital", "smart", "precisao", "precision"))
        else "CONVENCIONAL"
    )


def _finalidade(texto: str) -> str:
    t = normalizar(texto)
    return "SILAGEM" if any(k in t for k in ("silag", "silage")) else "GRAO"


def importar_fields(db: Session, arquivo: Path) -> dict[str, int]:
    """Cria os talhões e devolve o mapa identificador-FarmLab → id no banco."""
    df = _ler(arquivo)
    c_nome = _coluna(df, "field_name", "name", "nome", "field", "talhao")
    c_id = _coluna(df, "field_id", "id", "fid")
    c_area = _coluna(df, "area_ha", "area", "hectares", "ha")
    c_cultura = _coluna(df, "crop", "cultura")
    c_sistema = _coluna(df, "system", "sistema", "management", "manejo", "treatment")
    c_final = _coluna(df, "purpose", "finalidade", "use", "destination")
    c_geo = _coluna(df, "geometry", "geometria", "wkt", "geom")
    if c_nome is None:
        raise SystemExit(f"{arquivo.name}: coluna de nome do talhão não encontrada ({list(df.columns)})")
    apelidos = {}
    for _, linha in df.iterrows():
        nome = str(linha[c_nome]).strip()
        rotulo = " ".join(str(linha[c]) for c in (c_sistema, c_final) if c) + " " + nome
        area = ingestao.converter_numero(linha[c_area]) if c_area else 0
        t = garantir_talhao(
            db,
            nome,
            area or 0,
            (linha[c_cultura] if c_cultura else None) or "Milho",
            _sistema(linha[c_sistema] if c_sistema else rotulo),
            _finalidade(linha[c_final] if c_final else rotulo),
            linha[c_geo] if c_geo and str(linha[c_geo]).upper().startswith("POLYGON") else None,
        )
        apelidos[nome] = t.id
        if c_id:
            apelidos[str(linha[c_id]).strip()] = t.id
    log.info("Talhões: %d", len(apelidos))
    return apelidos


def importar_pragas(db: Session, arquivo: Path) -> None:
    df = _ler(arquivo)
    c_nome = _coluna(df, "pest_name", "name", "nome", "pest", "praga")
    c_cient = _coluna(df, "scientific_name", "nome_cientifico", "species")
    c_cultura = _coluna(df, "crop", "cultura")
    c_alerta = _coluna(df, "alert_threshold", "limiar_alerta", "alert")
    c_controle = _coluna(df, "control_threshold", "limiar_controle", "action_threshold", "control")
    c_dano = _coluna(
        df, "damage_threshold", "limiar_dano", "economic_threshold", "economic_injury_level", "damage"
    )
    def num(linha, col, padrao):
        valor = ingestao.converter_numero(linha[col]) if col else None
        return valor if valor is not None else padrao

    for _, linha in df.iterrows():
        alerta = num(linha, c_alerta, 2)
        controle = num(linha, c_controle, max(alerta, 5))
        garantir_praga(
            db,
            str(linha[c_nome]).strip(),
            linha[c_cient] if c_cient else None,
            linha[c_cultura] if c_cultura else "Milho",
            alerta,
            controle,
            num(linha, c_dano, max(controle, 10)),
        )


def importar_tabela(db: Session, arquivo: Path, tipo: TipoUpload, apelidos: dict[str, int]) -> None:
    r = ingestao.importar(db, tipo, arquivo.read_bytes(), arquivo.name, None, apelidos)
    log.info("%s (%s): %d ok, %d com erro", arquivo.name, tipo.value, r["linhas_ok"], r["linhas_erro"])
    for erro in r["erros"][:5]:
        log.warning("  linha %s: %s", erro["linha"], erro["erro"])


def _bboxes_da_linha(linha, df, largura, altura) -> list[dict]:
    """Aceita coluna JSON (bbox/bboxes) ou colunas x_min/y_min/x_max/y_max ou x/y/w/h, em pixel ou 0–1."""
    c_json = _coluna(df, "bboxes", "bbox", "boxes", "bounding_boxes")
    brutas = []
    if c_json and isinstance(linha[c_json], str) and linha[c_json].strip():
        valor = json.loads(linha[c_json])
        brutas = (
            valor if isinstance(valor, list) and valor and isinstance(valor[0], (list, dict)) else [valor]
        )
    else:
        cx0, cy0 = _coluna(df, "x_min", "xmin", "x1", "left"), _coluna(df, "y_min", "ymin", "y1", "top")
        cx1, cy1 = _coluna(df, "x_max", "xmax", "x2", "right"), _coluna(df, "y_max", "ymax", "y2", "bottom")
        cx, cy, cw, ch = (_coluna(df, n) for n in ("x", "y", "w", "h"))
        if all((cx0, cy0, cx1, cy1)):
            x0, y0, x1, y1 = (ingestao.converter_numero(linha[c]) for c in (cx0, cy0, cx1, cy1))
            brutas = [[x0, y0, x1 - x0, y1 - y0]]
        elif all((cx, cy, cw, ch)):
            brutas = [[ingestao.converter_numero(linha[c]) for c in (cx, cy, cw, ch)]]
    caixas = []
    for b in brutas:
        x, y, w, h = (b.get(k) for k in ("x", "y", "w", "h")) if isinstance(b, dict) else b[:4]
        if None in (x, y, w, h):
            continue
        if max(x, y, w, h) > 1.0001:  # pixels → normaliza
            x, w = x / largura, w / largura
            y, h = y / altura, h / altura
        caixas.append({"x": round(x, 4), "y": round(y, 4), "w": round(w, 4), "h": round(h, 4)})
    return caixas


def importar_armadilhas(db: Session, arquivo: Path, apelidos: dict[str, int], data_dir: Path) -> None:
    df = _ler(arquivo)
    c_talhao = _coluna(df, "field_id", "field", "field_name", "talhao", "talhao_id")
    c_data = _coluna(df, "datetime", "date_time", "timestamp", "date", "data")
    c_praga = _coluna(df, "pest_name", "pest", "praga", "species", "label", "class")
    c_contagem = _coluna(df, "count", "contagem", "n", "quantity")
    c_img = _coluna(df, "image", "image_name", "image_path", "filename", "file", "imagem")
    if not (c_talhao and c_data):
        raise SystemExit(f"{arquivo.name}: preciso de colunas de talhão e data ({list(df.columns)})")
    pragas = {normalizar(p.nome): p for p in db.scalars(select(Praga))}
    grupos: dict[tuple, dict] = defaultdict(lambda: {"caixas": [], "contagem": 0.0})
    for _, linha in df.iterrows():
        talhao_id = apelidos.get(str(linha[c_talhao]).strip()) or apelidos.get(normalizar(linha[c_talhao]))
        praga = pragas.get(normalizar(linha[c_praga])) if c_praga else next(iter(pragas.values()), None)
        if talhao_id is None or praga is None:
            continue
        quando = ingestao.converter_data(linha[c_data], com_hora=True)
        imagem_nome = str(linha[c_img]).strip() if c_img and pd.notna(linha[c_img]) else None
        chave = (talhao_id, praga.id, quando, imagem_nome)
        largura, altura = 1, 1
        if imagem_nome:
            achada = next(iter(data_dir.rglob(Path(imagem_nome).name)), None)
            grupos[chave]["origem"] = achada
            if achada is not None:
                lida = cv2.imread(str(achada))
                if lida is not None:
                    altura, largura = lida.shape[:2]
        caixas = _bboxes_da_linha(linha, df, largura, altura)
        grupos[chave]["caixas"] += caixas
        grupos[chave]["contagem"] += (
            ingestao.converter_numero(linha[c_contagem]) or 0 if c_contagem else len(caixas)
        )
    for (talhao_id, praga_id, quando, _), g in grupos.items():
        caminho = None
        if g.get("origem") is not None:
            caminho = f"armadilhas/{g['origem'].name}"
            destino = storage.caminho_absoluto(caminho)
            destino.parent.mkdir(parents=True, exist_ok=True)
            destino.write_bytes(g["origem"].read_bytes())
        registrar_armadilha(
            db, talhao_id, db.get(Praga, praga_id), quando, g["contagem"], g["caixas"], caminho
        )
    log.info("Armadilhas: %d eventos", len(grupos))


def seed_arquivos(db: Session, data_dir: Path) -> None:
    log.info("Importando FarmLab de %s", data_dir)
    fields = _achar(data_dir, "fields.*")
    if not fields:
        raise SystemExit(f"fields.csv não encontrado em {data_dir}")
    apelidos = importar_fields(db, fields[0])
    for arquivo in _achar(data_dir, "pest_details.*"):
        importar_pragas(db, arquivo)
    garantir_produtos(db)
    for padroes, tipo in (
        (("*metos*", "*Metos*", "*clima*", "*weather*"), TipoUpload.CLIMA),
        (("*cropman*", "*Cropman*", "*solo*", "*soil*"), TipoUpload.SOLO),
        (("ndvi_metadata.*", "*ndvi*"), TipoUpload.NDVI),
        (("*ekos*", "*EKOS*", "*colheita*", "*harvest*", "*yield*"), TipoUpload.COLHEITA),
    ):
        arquivos = _achar(data_dir, *padroes)
        if not arquivos:
            log.warning("Nenhum arquivo de %s encontrado (%s)", tipo.value, ", ".join(padroes))
        for arquivo in arquivos:
            importar_tabela(db, arquivo, tipo, apelidos)
    for arquivo in _achar(data_dir, "traps_events.*"):
        importar_armadilhas(db, arquivo, apelidos, data_dir)
    finalizar(db)


# ---------------------------------------------------------------- entrada


def executar(db: Session, data_dir: Path | None, demo: bool) -> None:
    garantir_usuarios(db)
    if demo or data_dir is None or not data_dir.exists():
        seed_demo(db)
    else:
        seed_arquivos(db, data_dir)


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--data-dir", type=Path, default=DATA_DIR_PADRAO)
    parser.add_argument("--demo", action="store_true", help="usa dados sintéticos mesmo que existam arquivos")
    args = parser.parse_args(argv)
    if not args.demo and not args.data_dir.exists():
        log.warning("%s não existe; usando dados de demonstração", args.data_dir)
    inicio = datetime.now()
    with SessionLocal() as db:
        executar(db, args.data_dir, args.demo)
    log.info(
        "Seed concluído em %.1fs. Login: %s / %s",
        (datetime.now() - inicio).total_seconds(),
        USUARIOS[0][1],
        USUARIOS[0][2],
    )


if __name__ == "__main__":
    sys.exit(main())
