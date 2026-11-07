from datetime import date, datetime
from types import SimpleNamespace

from google.genai import errors

from app.core.config import settings
from app.models import Imagem, LeituraClima, MetricaTalhao, Praga, Produto, Talhao
from app.models.enums import ClasseProduto, Finalidade, Sistema, StatusImagem, TipoImagem
from app.services.assistente import assistenteModelos
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


# ---------------------------------------------------------------- cota, modelos de reserva e cache


def _erro_429(atraso="3600s"):
    corpo = {
        "error": {
            "code": 429,
            "details": [
                {"violations": [{"quotaId": "GenerateRequestsPerDayPerProjectPerModel-FreeTier"}]},
                {"retryDelay": atraso},
            ],
        }
    }
    return errors.ClientError(429, corpo)


def _cliente_falso(monkeypatch, comportamento, chamadas):
    """Instala um Gemini falso: `comportamento(modelo, config)` devolve o texto ou levanta o erro."""

    class ClienteFalso:
        def __init__(self, api_key, http_options=None):
            self.models = SimpleNamespace(generate_content=self._gerar)

        def _gerar(self, model, contents, config):
            chamadas.append(model)
            return SimpleNamespace(text=comportamento(model, config))

    monkeypatch.setattr(settings, "gemini_api_key", "chave-falsa")
    monkeypatch.setattr(assistente.genai, "Client", ClienteFalso)


def _pergunta(client, token, texto):
    return client.post("/api/assistente/chat", json={"mensagem": texto}, headers=auth(token))


def test_cadeia_de_modelos_e_espera_do_erro():
    principal, leve = settings.gemini_modelo, settings.gemini_modelo_leve
    assert assistenteModelos.cadeia()[:2] == [principal, leve]
    assert assistenteModelos.cadeia(leve_primeiro=True)[0] == leve
    assert len(set(assistenteModelos.cadeia())) == len(assistenteModelos.cadeia())  # sem repetir
    assert assistenteModelos.segundos_do_erro(_erro_429("55739s")) == 55739
    assert (
        assistenteModelos.segundos_do_erro(errors.ClientError(429, {})) == assistenteModelos.ESPERA_PADRAO_S
    )
    assert assistenteModelos.descricao_espera(55739) == "cerca de 15 h"
    assert assistenteModelos.descricao_espera(2400) == "cerca de 40 min"
    assert assistenteModelos.descricao_espera(20) == "menos de 1 min"


def test_modelo_de_reserva_assume_no_429_sem_duplicar_paineis(client, db, agronomo_token, monkeypatch):
    _popular(db)
    chamadas = []
    principal = settings.gemini_modelo

    def comportamento(modelo, config):
        ferramentas = {f.__name__: f for f in config.tools}
        ferramentas["mostrar_grafico"]("ndvi")  # a tentativa já registrou um painel...
        if modelo == principal:
            raise _erro_429()  # ...e o modelo principal estoura a cota no meio
        return "Respondido pela reserva."

    _cliente_falso(monkeypatch, comportamento, chamadas)
    r = _pergunta(client, agronomo_token, "mostre o ndvi")
    assert r.status_code == 200
    corpo = r.json()
    assert corpo["resposta"] == "Respondido pela reserva."
    assert chamadas == [principal, settings.gemini_modelo_leve]
    assert len(corpo["paineis"]) == 1  # o painel da tentativa abandonada foi descartado

    # o principal ficou bloqueado: a próxima pergunta já começa pela reserva, sem gastar requisição nele
    chamadas.clear()
    assert _pergunta(client, agronomo_token, "outra pergunta").status_code == 200
    assert chamadas == [settings.gemini_modelo_leve]


def test_todos_sem_cota_avisa_quando_volta_e_para_de_tentar(client, agronomo_token, monkeypatch):
    chamadas = []

    def sempre_429(modelo, config):
        raise _erro_429("7200s")

    _cliente_falso(monkeypatch, sempre_429, chamadas)
    r = _pergunta(client, agronomo_token, "oi")
    assert r.status_code == 429 and "cerca de 2 h" in r.json()["detail"]
    tentativas = len(chamadas)
    assert tentativas == len(assistenteModelos.cadeia())  # tentou cada modelo uma vez
    r2 = _pergunta(client, agronomo_token, "oi de novo")
    assert r2.status_code == 429 and len(chamadas) == tentativas  # tudo bloqueado: nenhuma chamada nova


def test_modelo_inexistente_e_pulado(client, agronomo_token, monkeypatch):
    chamadas = []

    def comportamento(modelo, config):
        if modelo == settings.gemini_modelo:
            raise errors.ClientError(404, {"error": {"code": 404}})
        return "ok"

    _cliente_falso(monkeypatch, comportamento, chamadas)
    assert _pergunta(client, agronomo_token, "oi").json()["resposta"] == "ok"
    assert chamadas == [settings.gemini_modelo, settings.gemini_modelo_leve]


def test_resposta_repetida_sai_do_cache_com_os_paineis(client, db, agronomo_token, monkeypatch):
    _popular(db)
    chamadas = []

    def comportamento(modelo, config):
        {f.__name__: f for f in config.tools}["mostrar_grafico"]("ndvi")
        return "Gráfico pronto."

    _cliente_falso(monkeypatch, comportamento, chamadas)
    primeira = _pergunta(client, agronomo_token, "mostre o ndvi").json()
    segunda = _pergunta(client, agronomo_token, "mostre o ndvi").json()
    assert len(chamadas) == 1  # a segunda não gastou requisição
    assert primeira == segunda and len(segunda["paineis"]) == 1
    _pergunta(client, agronomo_token, "mostre o clima")  # pergunta diferente: chama de novo
    assert len(chamadas) == 2


def test_resumo_dos_talhoes_vai_no_prompt_e_o_limite_de_passos_e_menor(
    client, db, agronomo_token, monkeypatch
):
    _popular(db)
    visto = {}

    def comportamento(modelo, config):
        visto["sistema"] = config.system_instruction
        visto["passos"] = config.automatic_function_calling.maximum_remote_calls
        return "ok"

    _cliente_falso(monkeypatch, comportamento, [])
    _pergunta(client, agronomo_token, "quantos talhões?")
    assert "T1" in visto["sistema"] and "id | nome" in visto["sistema"]  # o modelo já sabe os ids
    assert "paralelo" in visto["sistema"]
    assert visto["passos"] == assistente.MAX_CHAMADAS_TOOLS == 4


# --------------------------------------------------------- gráfico analítico (NDVI x chuva + anotações)


def _com_clima_e_ndvi(db):
    """Dois talhões com NDVI em datas esparsas e 8 dias de clima, com uma chuva forte no dia 6."""
    a, b = _dois_talhoes(db)
    db.query(MetricaTalhao).delete()
    for talhao, valores in ((a, [0.40, 0.70, 0.30, 0.55]), (b, [0.50, 0.60, 0.58, 0.62])):
        for dia, valor in zip((2, 4, 7, 9), valores, strict=True):
            db.add(MetricaTalhao(talhao_id=talhao.id, data=date(2026, 1, dia), ndvi_medio=valor))
    chuvas = {1: 0, 2: 3, 3: 0, 4: 0, 5: 12, 6: 80, 7: 0, 8: 5}
    for dia, mm in chuvas.items():
        db.add(LeituraClima(data_hora=datetime(2026, 1, dia, 12), chuva_mm=mm, temp_med=25.0))
    db.commit()
    return a, b


def test_grafico_analitico_junta_ndvi_chuva_e_anota_os_eventos(db):
    a, b = _com_clima_e_ndvi(db)
    paineis = []
    tools = {f.__name__: f for f in criar_tools(db, paineis)}
    resumo = tools["mostrar_grafico_analitico"](talhao_ids=[a.id, b.id])
    assert resumo["mostrado"] == "grafico_combinado"

    spec = paineis[0]
    assert set(spec["eixos"]) == {"esq", "dir"}
    tipos = {(s["id"], s["tipo"], s["eixo"]) for s in spec["series"]}
    assert (f"t{a.id}", "linha", "esq") in tipos and ("clima", "barra", "dir") in tipos

    rotulos = {n["rotulo"]: n for n in spec["anotacoes"]}
    assert rotulos["Chuva forte: 80 mm"]["data"] == "2026-01-06"
    assert any(r.startswith("Pico de NDVI 0,70") for r in rotulos)
    assert any(r.startswith("NDVI caiu 0,40") for r in rotulos)  # T1: 0,70 -> 0,30
    assert [n["id"] for n in spec["anotacoes"]] == list(range(1, len(spec["anotacoes"]) + 1))
    datas = [n["data"] for n in spec["anotacoes"]]
    assert datas == sorted(datas)  # em ordem de data

    # o modelo recebe números para analisar, e o aviso de que a chuva é da fazenda toda
    assert resumo["chuva"]["total_mm"] == 100 and resumo["chuva"]["dias_com_chuva"] == 4
    assert "UMA estação" in resumo["chuva"]["obs"]
    antes_depois = next(x for x in resumo["ndvi_antes_e_depois_das_chuvas_fortes"] if "80 mm" in x["chuva"])
    assert antes_depois["data"] == "2026-01-06"
    t1 = next(x for x in antes_depois["talhoes"] if x["nome"] == "T1")
    assert (t1["ndvi_antes"], t1["ndvi_depois"]) == (0.70, 0.30)


def test_notas_do_modelo_entram_com_limite_e_validacao(db):
    a, _ = _com_clima_e_ndvi(db)
    paineis = []
    tools = {f.__name__: f for f in criar_tools(db, paineis)}
    resumo = tools["mostrar_grafico_analitico"](
        talhao_ids=[a.id],
        notas=[
            "2026-01-05: chuva moderada antes da queda",
            "2026-01-07 : segunda nota",
            "data-ruim: x",  # data inválida
            "2030-01-01: fora do período",  # fora do período
        ],
    )
    notas = [n for n in paineis[0]["anotacoes"] if n["tipo"] == "ia"]
    assert [n["rotulo"] for n in notas] == ["chuva moderada antes da queda", "segunda nota"]
    assert resumo["notas_do_modelo_ignoradas"] == 1  # só 3 cabem; destas, 1 é inválida


def test_grafico_analitico_sem_anotacoes_e_so_com_ndvi(db):
    a, _ = _com_clima_e_ndvi(db)
    paineis = []
    tools = {f.__name__: f for f in criar_tools(db, paineis)}
    tools["mostrar_grafico_analitico"](talhao_ids=[a.id], complemento=None, anotar=False)
    spec = paineis[0]
    assert spec["anotacoes"] == [] and set(spec["eixos"]) == {"esq"}
    assert [s["id"] for s in spec["series"]] == [f"t{a.id}"]


def test_grafico_analitico_respeita_o_periodo_e_valida_parametros(db):
    a, _ = _com_clima_e_ndvi(db)
    paineis = []
    tools = {f.__name__: f for f in criar_tools(db, paineis)}
    tools["mostrar_grafico_analitico"](talhao_ids=[a.id], de="2026-01-05", ate="2026-01-08")
    clima = next(s for s in paineis[0]["series"] if s["id"] == "clima")
    assert [p["data"] for p in clima["pontos"]] == ["2026-01-05", "2026-01-06", "2026-01-07", "2026-01-08"]
    serie = next(s for s in paineis[0]["series"] if s["id"] == f"t{a.id}")
    assert [p["data"] for p in serie["pontos"]] == ["2026-01-07"]

    assert "erro" in tools["mostrar_grafico_analitico"](metrica="outra")
    assert "erro" in tools["mostrar_grafico_analitico"](complemento="neve")
    assert "erro" in tools["mostrar_grafico_analitico"](de="ontem")
    assert "erro" in tools["mostrar_grafico_analitico"](talhao_ids=[a.id], de="2030-01-01", ate="2030-02-01")
