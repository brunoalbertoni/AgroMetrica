from datetime import date, datetime
from types import SimpleNamespace

from app.core.config import settings
from app.models import Imagem, MetricaTalhao, Praga, Produto, Talhao
from app.models.enums import ClasseProduto, Finalidade, Sistema, StatusImagem, TipoImagem
from app.services.assistente import assistenteService as assistente
from app.services.assistente.assistenteTools import criar_tools
from app.services.diagnosticos import diagnosticosService

from .conftest import auth


def _popular(db):
    t = Talhao(nome="T1", area_ha=10, cultura="Milho", sistema=Sistema.AGRO_4_0, finalidade=Finalidade.GRAO)
    db.add(t)
    db.add(
        Produto(
            nome_comercial="Calcário", classe=ClasseProduto.CORRETIVO, dose_min=1, dose_max=2, unidade="kg/ha"
        )
    )
    db.add(Praga(nome="Spodoptera", cultura="Milho", limiar_alerta=1, limiar_controle=2, limiar_dano=3))
    db.commit()
    db.add(MetricaTalhao(talhao_id=t.id, data=date(2026, 1, 10), ndvi_medio=0.71))
    db.commit()
    return t


def _tools(db):
    return {f.__name__: f for f in criar_tools(db)}


def test_tools_consultam_o_banco(db):
    t = _popular(db)
    tools = _tools(db)
    assert tools["resumo_geral"]()["cards"]["talhoes"] == 1
    assert tools["listar_produtos"]()["produtos"][0]["nome_comercial"] == "Calcário"
    assert tools["listar_pragas"]()["pragas"][0]["nome"] == "Spodoptera"
    assert tools["serie_ndvi"](t.id)["pontos"][0]["ndvi_medio"] == 0.71
    assert tools["consultar_talhao"](t.id)["talhao"]["nome"] == "T1"
    assert "geometria" not in tools["consultar_talhao"](t.id)["talhao"]
    assert tools["listar_alertas"]() == {"alertas": []}
    assert tools["listar_diagnosticos"](severidade="alta")["diagnosticos"] == []
    assert "dias" in tools["clima_diario"](5)


def test_tool_devolve_erro_em_vez_de_levantar(db):
    tools = _tools(db)
    assert "erro" in tools["consultar_talhao"](999)
    assert "erro" in tools["listar_diagnosticos"](severidade="NADA")


def test_chat_exige_login(client):
    assert client.post("/api/assistente/chat", json={"mensagem": "oi"}).status_code == 401


def test_chat_sem_chave_devolve_503(client, agronomo_token, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "")
    r = client.post("/api/assistente/chat", json={"mensagem": "oi"}, headers=auth(agronomo_token))
    assert r.status_code == 503


def test_chat_entrega_tools_ao_modelo(client, agronomo_token, monkeypatch):
    monkeypatch.setattr(settings, "gemini_api_key", "chave-falsa")
    chamadas = {}

    class ClienteFalso:
        def __init__(self, api_key, http_options=None):
            self.models = SimpleNamespace(generate_content=self._gerar)

        def _gerar(self, model, contents, config):
            chamadas["tools"] = [f.__name__ for f in config.tools]
            chamadas["sistema"] = config.system_instruction
            chamadas["contents"] = contents
            return SimpleNamespace(text="Resposta de teste")

    monkeypatch.setattr(assistente.genai, "Client", ClienteFalso)
    r = client.post(
        "/api/assistente/chat",
        json={"mensagem": "Quais produtos?", "historico": [{"papel": "usuario", "texto": "oi"}]},
        headers=auth(agronomo_token),
    )
    assert r.status_code == 200
    assert r.json() == {"resposta": "Resposta de teste", "paineis": []}
    assert "listar_produtos" in chamadas["tools"] and "resumo_geral" in chamadas["tools"]
    assert len(chamadas["contents"]) == 2


def _dois_talhoes(db):
    a = _popular(db)
    b = Talhao(
        nome="T2", area_ha=8, cultura="Milho", sistema=Sistema.CONVENCIONAL, finalidade=Finalidade.GRAO
    )
    db.add(b)
    db.commit()
    db.add(MetricaTalhao(talhao_id=b.id, data=date(2026, 1, 10), ndvi_medio=0.55))
    db.commit()
    return a, b


def test_mostrar_grafico_gera_painel_e_resumo(db):
    a, b = _dois_talhoes(db)
    paineis = []
    tools = {f.__name__: f for f in criar_tools(db, paineis)}
    retorno = tools["mostrar_grafico"]("ndvi", [a.id, b.id])
    assert retorno["mostrado"] == "grafico_linhas"
    assert [s["nome"] for s in retorno["series"]] == ["T1", "T2"]  # o modelo recebe só o resumo
    assert paineis[0]["series"][0]["pontos"] == [{"data": "2026-01-10", "valor": 0.71}]
    assert "erro" in tools["mostrar_grafico"]("metrica-inexistente")


def test_mostrar_comparativo_destaca_o_melhor(db):
    a, b = _dois_talhoes(db)
    paineis = []
    tools = {f.__name__: f for f in criar_tools(db, paineis)}
    tools["mostrar_comparativo"](a.id, b.id)
    ndvi = next(i for i in paineis[0]["indicadores"] if i["rotulo"] == "NDVI médio da safra")
    assert ndvi["melhor"] == "a"
    pragas = next(i for i in paineis[0]["indicadores"] if i["rotulo"] == "Pragas capturadas")
    assert pragas["melhor"] is None and pragas["sem_dados"] == ["a", "b"]  # sem armadilha: sem vencedor
    assert "erro" in tools["mostrar_comparativo"](a.id, a.id)


def test_mostrar_galeria_traz_foto_e_caixas(db):
    t = _popular(db)
    praga = db.query(Praga).first()
    img = Imagem(
        talhao_id=t.id,
        tipo=TipoImagem.ARMADILHA,
        caminho="farmlab/armadilhas/a.jpg",
        data_captura=datetime(2026, 1, 10, 8),
        status=StatusImagem.PROCESSADO,
    )
    db.add(img)
    db.commit()
    caixa = {"x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2, "rotulo": "Spodoptera", "confianca": 0.9}
    diagnosticosService.registrar_armadilha(
        db, t.id, praga.id, contagem=5, data=datetime(2026, 1, 10, 8), imagem_id=img.id, bboxes=[caixa]
    )
    paineis = []
    tools = {f.__name__: f for f in criar_tools(db, paineis)}
    assert tools["mostrar_galeria_pragas"](praga="spod")["mostrado"] == "galeria_pragas"
    item = paineis[0]["itens"][0]
    assert item["contagem"] == 5 and item["bboxes"] == [caixa] and item["imagem_url"].endswith("a.jpg")
    assert "erro" in tools["mostrar_galeria_pragas"](praga="nao-existe")


def test_limite_de_paineis_por_resposta(db):
    _dois_talhoes(db)
    paineis = []
    tools = {f.__name__: f for f in criar_tools(db, paineis)}
    assert "mostrado" in tools["mostrar_grafico"]("ndvi")
    assert "mostrado" in tools["mostrar_grafico"]("ndvi")
    assert len(paineis) == 2
    assert "erro" in tools["mostrar_grafico"]("ndvi")  # o terceiro é recusado
    assert len(paineis) == 2


def test_chat_devolve_os_paineis_das_tools(client, db, agronomo_token, monkeypatch):
    _popular(db)
    monkeypatch.setattr(settings, "gemini_api_key", "chave-falsa")

    class ClienteFalso:
        def __init__(self, api_key, http_options=None):
            self.models = SimpleNamespace(generate_content=self._gerar)

        def _gerar(self, model, contents, config):
            # simula o SDK executando a tool que o Gemini pediu
            {f.__name__: f for f in config.tools}["mostrar_grafico"]("ndvi")
            return SimpleNamespace(text="Veja o gráfico.")

    monkeypatch.setattr(assistente.genai, "Client", ClienteFalso)
    r = client.post("/api/assistente/chat", json={"mensagem": "mostre o ndvi"}, headers=auth(agronomo_token))
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["resposta"] == "Veja o gráfico."
    assert [p["tipo"] for p in corpo["paineis"]] == ["grafico_linhas"]
