# AgroMétrica

Monitoramento de talhões de milho: NDVI, clima, solo, armadilhas de pragas e produtividade,
com diagnóstico por regras, prescrição sugerida e o comparativo entre o manejo 4.0 e o convencional.

- **Backend**: FastAPI + SQLAlchemy 2 + Alembic, MySQL 8 (Docker)
- **Frontend**: React (Vite) + TanStack Query/Table + Recharts + Leaflet + Tailwind
- Especificação: [docs/spec.md](docs/spec.md) · Plano de implementação: [docs/plans/agrometrica-mvp.md](docs/plans/agrometrica-mvp.md)

## Como rodar (Windows)

Pré-requisitos: Python 3.12+, Node.js 20+, Docker Desktop.

```powershell
# 1. Banco (MySQL 8 na porta 3307 do host, para não conflitar com um MySQL local na 3306)
copy .env.example .env
# edite o .env e troque JWT_SECRET; para gerar um valor:
python -c "import secrets; print(secrets.token_urlsafe(48))"
docker compose up -d
docker compose ps                       # espere o serviço db aparecer como (healthy), ~30 s na 1ª vez

# 2. Backend
cd backend
python -m venv .venv
.venv\Scripts\activate                  # se o PowerShell bloquear: Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
pip install -r requirements.txt
alembic upgrade head
python -m scripts.seed_farmlab --limpar # importa data/raw/farmlab (ver "Dados do FarmLab")
uvicorn app.main:app --reload           # http://localhost:8000/docs

# 3. Frontend (outro terminal)
cd frontend
npm install
npm run dev                             # http://localhost:5173
```

Sem um `JWT_SECRET` próprio no `.env`, a API usa um segredo aleatório a cada início (e avisa no log):
os logins caem sempre que o servidor reinicia.

Usuários criados pelo seed (troque as senhas fora do ambiente de desenvolvimento):

| Perfil | E-mail | Senha |
|---|---|---|
| Administrador | admin@agrometrica.com.br | admin123 |
| Agrônomo | agronomo@agrometrica.com.br | agro123 |

## Dados do FarmLab

O sistema não tem dados inventados: tudo vem do dataset FarmLab. Coloque as pastas do dataset em
`data/raw/farmlab/` (fica fora do git) e rode `python -m scripts.seed_farmlab`. Os arquivos são procurados
em qualquer subpasta:

| Arquivo | Vira |
|---|---|
| EKOS `fields.csv` | talhões (nome, área, sistema e finalidade pelo nome, polígono) |
| EKOS `pest_details.csv` | pragas do milho com os limiares de alerta, controle e dano |
| Metos `Relatório Horário….csv` | clima horário (ETP diária na leitura das 00:00) e balanço hídrico |
| OneSoil `ndvi_metadata.csv` + `JPG/` | NDVI por talhão e data e o mapa de NDVI (talhão achado pela posição da imagem) |
| EKOS `LAYER_MAP_FERTILIZATION.csv` / `LAYER_MAP_PLANTING.csv` | calagem, gessagem, adubação de plantio e plantio por talhão (aba Manejo) |
| EKOS `LAYER_MAP_GRAIN_HARVESTING.csv` | produtividade: só trechos de colheita dentro dos talhões |
| EKOS `agricultural_inputs.csv` | catálogo (corretivos e sementes, com a faixa de dose aplicada) |
| EKOS `traps_list/traps_data/traps_events.csv` | diagnósticos de praga por foto, com as caixas da detecção automática |
| Cropman `soil_analysis.csv` + `amostras_solo.csv` | análise de solo (0–20 e 20–40 cm) |

- A análise do Cropman não diz de qual talhão é cada amostra. Crie `data/raw/farmlab/amostras_solo.csv`
  com as colunas `amostra;talhao;data_coleta` (talhão pelo nome ou pelo idField do EKOS) para importá-la.
- As fotos das armadilhas são baixadas do S3 do EKOS na primeira execução (`--sem-fotos` pula o download).
  As das armadilhas eletrônicas não estão mais disponíveis (404): entram só as contagens.
- A camada de colheita do dataset não tem trechos dentro dos 4 talhões, então não há produtividade.
- Inseticidas e fungicidas não fazem parte do dataset: cadastre-os no catálogo e vincule às pragas para que
  os diagnósticos de praga gerem prescrições.
- `--limpar` apaga os dados agronômicos antes de importar (usuários ficam). Sem ele, o seed atualiza sem duplicar.

## Regras e limiares

Limiares de NDVI, balanço hídrico, solo e janela de aplicação ficam em
[backend/app/core/regras.toml](backend/app/core/regras.toml). Os limiares de praga ficam no cadastro de pragas.
As prescrições são sempre **sugestões** e precisam ser validadas por um responsável técnico.

## Desenvolvimento

```powershell
cd backend;  ruff check . ; pytest          # os testes usam SQLite, não precisam do MySQL
cd frontend; npm run lint ; npm run build
```

- Toda mudança de tabela passa pelo Alembic: `alembic revision --autogenerate -m "..."` e `alembic upgrade head`.
- Branches: `main` (estável), `dev`, `feat/nome-curto`. Merge em `dev` por pull request com o CI verde.
- Commits: `feat:`, `fix:`, `docs:`, `refactor:`, `test:`.
