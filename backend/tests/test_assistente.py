from datetime import date
from types import SimpleNamespace

from app.core.config import settings
from app.models import MetricaTalhao, Praga, Produto, Talhao
from app.models.enums import ClasseProduto, Finalidade, Sistema
from app.services import assistente
from app.services.assistente_tools import criar_tools

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
    assert r.json() == {"resposta": "Resposta de teste"}
    assert "listar_produtos" in chamadas["tools"] and "resumo_geral" in chamadas["tools"]
    assert len(chamadas["contents"]) == 2
