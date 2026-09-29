from datetime import datetime

from sqlalchemy import func, select

from app.models import Alerta, Diagnostico, Imagem, MetricaTalhao, Praga, Prescricao, Produto, Talhao, Usuario
from app.services import diagnostico as diag_svc
from app.services import storage
from scripts import seed_farmlab


def _contar(db, modelo):
    return db.scalar(select(func.count()).select_from(modelo))


def test_seed_demo_popula_banco(db):
    seed_farmlab.executar(db, data_dir=None, demo=True)

    assert _contar(db, Talhao) == 4
    assert {t.sistema for t in db.scalars(select(Talhao))} == {"AGRO_4_0", "CONVENCIONAL"}
    assert db.scalar(select(Usuario).where(Usuario.perfil == "ADMIN")) is not None
    assert db.scalar(select(Usuario).where(Usuario.perfil == "AGRONOMO")) is not None

    for t in db.scalars(select(Talhao)):
        datas_ndvi = db.scalar(
            select(func.count()).where(MetricaTalhao.talhao_id == t.id, MetricaTalhao.ndvi_medio.is_not(None))
        )
        assert datas_ndvi == 49
        prod = db.scalar(
            select(func.count()).where(
                MetricaTalhao.talhao_id == t.id, MetricaTalhao.produtividade_kg_ha.is_not(None)
            )
        )
        assert prod == 1

    armadilhas = db.scalars(select(Diagnostico).where(Diagnostico.tipo == "PRAGA")).all()
    com_bbox = [d for d in armadilhas if d.detalhes["bboxes"]]
    assert com_bbox, "armadilhas devem trazer bounding boxes"
    for b in com_bbox[0].detalhes["bboxes"]:
        assert 0 <= b["x"] <= 1 and 0 <= b["y"] <= 1 and 0 < b["w"] <= 1 and 0 < b["h"] <= 1
    img = db.get(Imagem, com_bbox[0].imagem_id)
    assert img.tipo == "ARMADILHA" and storage.caminho_absoluto(img.caminho).exists()

    assert db.scalar(select(Alerta).where(Alerta.severidade == "ALTA")) is not None
    assert _contar(db, Prescricao) > 0
    assert _contar(db, Produto) > 0 and _contar(db, Praga) > 0

    # balanço hídrico calculado a partir do clima
    assert db.scalar(select(func.count()).where(MetricaTalhao.balanco_hidrico_mm.is_not(None))) > 0


def test_seed_e_idempotente(db):
    seed_farmlab.executar(db, data_dir=None, demo=True)
    antes = {m: _contar(db, m) for m in (Talhao, Diagnostico, Alerta, Prescricao, Produto, Praga, Usuario)}
    seed_farmlab.executar(db, data_dir=None, demo=True)
    depois = {m: _contar(db, m) for m in antes}
    assert antes == depois


def test_armadilha_repetida_nao_duplica(db):
    t = Talhao(nome="T", area_ha=1, cultura="Milho", sistema="AGRO_4_0", finalidade="GRAO")
    p = Praga(nome="Lagarta", limiar_alerta=1, limiar_controle=2, limiar_dano=3)
    db.add_all([t, p])
    db.commit()
    primeiro = diag_svc.registrar_armadilha(db, t.id, p.id, contagem=5, data=datetime(2024, 1, 1))
    segundo = diag_svc.registrar_armadilha(db, t.id, p.id, contagem=5, data=datetime(2024, 1, 1))
    assert segundo.id == primeiro.id
    assert _contar(db, Diagnostico) == 1 and _contar(db, Alerta) == 1


def test_seed_arquivos_reais(db, tmp_path):
    import cv2
    import numpy as np

    (tmp_path / "fields.csv").write_text(
        "field_id,field_name,area_ha,crop,system,purpose\n"
        "F1,Grain Digital,12.4,Milho,4.0,grain\n"
        "F2,Grain Conventional,11.8,Milho,conventional,grain\n",
        encoding="utf-8",
    )
    (tmp_path / "pest_details.csv").write_text(
        "pest_name,scientific_name,alert_threshold,control_threshold,damage_threshold\n"
        "Lagarta-do-cartucho,Spodoptera frugiperda,1,2,3\n",
        encoding="utf-8",
    )
    (tmp_path / "ndvi_metadata.csv").write_text(
        "field_id,date,ndvi_mean\nF1,2024-01-01,0.7\nF2,2024-01-01,0.6\n", encoding="utf-8"
    )
    cv2.imwrite(str(tmp_path / "trap1.jpg"), np.full((100, 200, 3), 200, dtype=np.uint8))
    (tmp_path / "traps_events.csv").write_text(
        "field_id;date;pest_name;image;x_min;y_min;x_max;y_max\n"
        "F2;05/01/2024 08:00;Lagarta-do-cartucho;trap1.jpg;20;10;60;30\n"
        "F2;05/01/2024 08:00;Lagarta-do-cartucho;trap1.jpg;100;50;140;90\n"
        "F2;05/01/2024 08:00;Lagarta-do-cartucho;trap1.jpg;150;20;190;40\n",
        encoding="utf-8",
    )
    seed_farmlab.executar(db, data_dir=tmp_path, demo=False)

    talhoes = {t.nome: t for t in db.scalars(select(Talhao))}
    assert talhoes["Grain Digital"].sistema == "AGRO_4_0"
    assert talhoes["Grain Conventional"].sistema == "CONVENCIONAL"
    assert _contar(db, MetricaTalhao) == 2
    diag = db.scalar(select(Diagnostico).where(Diagnostico.tipo == "PRAGA"))
    assert diag.talhao_id == talhoes["Grain Conventional"].id
    assert diag.severidade == "ALTA"  # 3 caixas ≥ limiar de dano 3
    assert diag.detalhes["bboxes"][0] == {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2}
    assert diag.detalhes["data"].startswith("2024-01-05")
