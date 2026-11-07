import json
from types import SimpleNamespace

import pytest
from google.genai import errors

from app.core.config import settings
from app.models import Talhao
from app.models.enums import CategoriaCampo, Finalidade, Sistema
from app.services.assistente import assistenteService
from app.services.campo import campoService

from .conftest import auth


@pytest.fixture(autouse=True)
def _sem_ia(monkeypatch):
    """Nos testes a IA fica desligada: vale o plano B por palavras-chave (determinístico)."""
    monkeypatch.setattr(settings, "gemini_api_key", "")


@pytest.fixture
def talhoes(db):
    a = Talhao(
        nome="Grão 4.0", area_ha=19, cultura="Milho", sistema=Sistema.AGRO_4_0, finalidade=Finalidade.GRAO
    )
    b = Talhao(
        nome="Silagem 4.0",
        area_ha=8,
        cultura="Milho",
        sistema=Sistema.AGRO_4_0,
        finalidade=Finalidade.SILAGEM,
    )
    c = Talhao(
        nome="Silagem",
        area_ha=5,
        cultura="Milho",
        sistema=Sistema.CONVENCIONAL,
        finalidade=Finalidade.SILAGEM,
    )
    db.add_all([a, b, c])
    db.commit()
    return a, b, c


@pytest.mark.parametrize(
    ("texto", "esperada"),
    [
        ("O pH do solo deu 5,2 e precisa de calcário", CategoriaCampo.SOLO),
        ("Muita lagarta e cigarrinha na armadilha hoje", CategoriaCampo.PRAGA),
        ("Choveu 40 mm e o vento estava forte", CategoriaCampo.CLIMA),
        ("Plantio terminado e a colheitadeira chega amanhã", CategoriaCampo.MANEJO),
        ("Cheguei cedo, tudo tranquilo", CategoriaCampo.OBSERVACAO),
    ],
)
def test_classificacao_por_palavras(texto, esperada):
    assert campoService.classificar_por_palavras(texto) == esperada


def test_talhao_de_nome_mais_longo_vence(talhoes):
    _, silagem40, _ = talhoes
    assert campoService.achar_talhao("lagarta na silagem 4.0 ontem", list(talhoes)).id == silagem40.id
    assert campoService.achar_talhao("nada a ver", list(talhoes)) is None


def test_criar_sugere_categoria_e_talhao(client, talhoes, agronomo_token):
    r = client.post(
        "/api/campo/mensagens",
        json={"texto": "Solo do Grão 4.0 com pH 5,1, calcário atrasado", "remetente": "Marcos"},
        headers=auth(agronomo_token),
    )
    assert r.status_code == 201
    m = r.json()
    assert m["categoria"] == "SOLO" and m["talhao_nome"] == "Grão 4.0"
    assert m["destino"] == "CAIXA_DE_ENTRADA" and m["classificada_por_ia"] is False
    assert m["remetente"] == "Marcos" and m["origem"] == "manual"


def test_mensagem_vazia_e_talhao_inexistente_sao_recusados(client, agronomo_token):
    h = auth(agronomo_token)
    assert client.post("/api/campo/mensagens", json={"texto": "   "}, headers=h).status_code == 400
    assert (
        client.post("/api/campo/mensagens", json={"texto": "oi", "talhao_id": 999}, headers=h).status_code
        == 404
    )


def test_endpoints_exigem_login(client):
    assert client.get("/api/campo/mensagens").status_code == 401
    assert client.post("/api/campo/mensagens", json={"texto": "oi"}).status_code == 401


def test_usuario_decide_o_destino_e_a_categoria(client, talhoes, agronomo_token):
    h = auth(agronomo_token)
    mid = client.post("/api/campo/mensagens", json={"texto": "valores de P e K baixos"}, headers=h).json()[
        "id"
    ]
    r = client.patch(
        f"/api/campo/mensagens/{mid}",
        json={
            "categoria": "SOLO",
            "destino": "DADO_SOLO",
            "talhao_id": talhoes[0].id,
            "nota": "  conferir no laudo ",
        },
        headers=h,
    )
    assert r.status_code == 200
    m = r.json()
    assert (m["categoria"], m["destino"], m["talhao_nome"], m["nota"]) == (
        "SOLO",
        "DADO_SOLO",
        "Grão 4.0",
        "conferir no laudo",
    )
    assert m["atualizado_em"] is not None
    # talhao_id null limpa o vínculo; sem mais campos, o resto fica como está
    limpo = client.patch(f"/api/campo/mensagens/{mid}", json={"talhao_id": None}, headers=h).json()
    assert limpo["talhao_id"] is None and limpo["destino"] == "DADO_SOLO"
    assert client.patch("/api/campo/mensagens/999", json={"nota": "x"}, headers=h).status_code == 404


def test_listagem_filtra_e_resumo_conta_por_categoria(client, talhoes, agronomo_token):
    h = auth(agronomo_token)
    ids = {}
    for chave, texto in {
        "solo": "ph do solo baixo",
        "praga1": "lagarta na armadilha",
        "praga2": "cigarrinha de novo",
        "obs": "dia tranquilo",
    }.items():
        ids[chave] = client.post("/api/campo/mensagens", json={"texto": texto}, headers=h).json()["id"]
    client.patch(f"/api/campo/mensagens/{ids['praga1']}", json={"destino": "ANOTACAO"}, headers=h)

    assert len(client.get("/api/campo/mensagens", headers=h).json()) == 4
    pragas = client.get("/api/campo/mensagens?categoria=PRAGA", headers=h).json()
    assert {m["id"] for m in pragas} == {ids["praga1"], ids["praga2"]}
    pend = client.get("/api/campo/mensagens?destino=CAIXA_DE_ENTRADA", headers=h).json()
    assert ids["praga1"] not in {m["id"] for m in pend}

    resumo = client.get("/api/campo/resumo", headers=h).json()
    assert resumo["total"] == 4 and resumo["pendentes"] == 3
    por = {c["categoria"]: c for c in resumo["categorias"]}
    assert por["PRAGA"] == {"categoria": "PRAGA", "total": 2, "pendentes": 1}
    assert por["CLIMA"]["total"] == 0 and len(resumo["categorias"]) == len(CategoriaCampo)


def test_analisar_guarda_o_texto_da_ia(client, talhoes, agronomo_token, monkeypatch):
    h = auth(agronomo_token)
    mid = client.post("/api/campo/mensagens", json={"texto": "lagarta no Grão 4.0"}, headers=h).json()["id"]
    pedidos = []

    def falso(db, pedido, historico):
        pedidos.append(pedido)
        return "Coerente com os dados.", []

    monkeypatch.setattr(assistenteService, "responder", falso)
    r = client.post(f"/api/campo/mensagens/{mid}/analisar", headers=h)
    assert r.status_code == 200 and r.json()["analise_ia"] == "Coerente com os dados."
    assert "lagarta no Grão 4.0" in pedidos[0] and "talhão Grão 4.0" in pedidos[0]


def test_analisar_sem_chave_devolve_503(client, talhoes, agronomo_token):
    h = auth(agronomo_token)
    mid = client.post("/api/campo/mensagens", json={"texto": "teste"}, headers=h).json()["id"]
    assert client.post(f"/api/campo/mensagens/{mid}/analisar", headers=h).status_code == 503


# ---------------------------------------------------------------- classificação por IA e cota


def _gemini_falso(monkeypatch, comportamento, chamadas):
    class ClienteFalso:
        def __init__(self, api_key, http_options=None):
            self.models = SimpleNamespace(generate_content=self._gerar)

        def _gerar(self, model, contents, config):
            chamadas.append(model)
            return SimpleNamespace(text=comportamento(model))

    monkeypatch.setattr(settings, "gemini_api_key", "chave-falsa")
    monkeypatch.setattr(campoService.genai, "Client", ClienteFalso)


def _json_ia(categoria="SOLO", talhao=None, resumo="pH baixo"):
    return json.dumps({"categoria": categoria, "talhao": talhao, "resumo": resumo})


def test_classificacao_comeca_pelo_modelo_leve_e_guarda_o_resumo(
    client, talhoes, agronomo_token, monkeypatch
):
    chamadas = []
    _gemini_falso(monkeypatch, lambda modelo: _json_ia("SOLO", "Silagem 4.0", "pH baixo no talhão"), chamadas)
    r = client.post("/api/campo/mensagens", json={"texto": "coletei amostra"}, headers=auth(agronomo_token))
    m = r.json()
    assert chamadas == [settings.gemini_modelo_leve]  # o principal fica para o chat
    assert (m["categoria"], m["talhao_nome"], m["resumo"], m["classificada_por_ia"]) == (
        "SOLO",
        "Silagem 4.0",
        "pH baixo no talhão",
        True,
    )


def test_classificacao_cai_para_o_proximo_modelo_no_429(client, talhoes, agronomo_token, monkeypatch):
    chamadas = []
    leve = settings.gemini_modelo_leve

    def comportamento(modelo):
        if modelo == leve:
            raise errors.ClientError(429, {"error": {"details": [{"retryDelay": "3600s"}]}})
        return _json_ia("CLIMA")

    _gemini_falso(monkeypatch, comportamento, chamadas)
    m = client.post("/api/campo/mensagens", json={"texto": "mensagem"}, headers=auth(agronomo_token)).json()
    assert m["categoria"] == "CLIMA" and m["classificada_por_ia"] is True
    assert chamadas[0] == leve and chamadas[1] != leve


def test_sem_cota_em_nenhum_modelo_usa_palavras_chave(client, talhoes, agronomo_token, monkeypatch):
    def sempre_429(modelo):
        raise errors.ClientError(429, {})

    _gemini_falso(monkeypatch, sempre_429, [])
    m = client.post(
        "/api/campo/mensagens", json={"texto": "muita lagarta hoje"}, headers=auth(agronomo_token)
    ).json()
    assert m["categoria"] == "PRAGA" and m["classificada_por_ia"] is False and m["resumo"] is None


def test_resposta_invalida_da_ia_cai_para_palavras_chave(client, talhoes, agronomo_token, monkeypatch):
    _gemini_falso(monkeypatch, lambda modelo: "isto não é json", [])
    m = client.post("/api/campo/mensagens", json={"texto": "pH baixo"}, headers=auth(agronomo_token)).json()
    assert m["categoria"] == "SOLO" and m["classificada_por_ia"] is False


def test_ia_nao_pode_inventar_categoria(client, talhoes, agronomo_token, monkeypatch):
    _gemini_falso(monkeypatch, lambda modelo: _json_ia("APAGAR_TUDO"), [])
    m = client.post(
        "/api/campo/mensagens", json={"texto": "dia tranquilo"}, headers=auth(agronomo_token)
    ).json()
    assert m["categoria"] == "OBSERVACAO" and m["classificada_por_ia"] is False
