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
python -m scripts.seed_farmlab          # usa data/raw/farmlab se existir; senão, dados de demonstração
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

Coloque os arquivos em `data/raw/farmlab/` (a pasta fica fora do git) e rode `python -m scripts.seed_farmlab`.
O seed procura, em qualquer subpasta:

| Arquivo | Vira |
|---|---|
| `fields.csv` | talhões (nome, área, sistema 4.0/convencional, grão/silagem, geometria WKT) |
| `pest_details.csv` | pragas e limiares de alerta, controle e dano |
| `*metos*.csv/xlsx` | clima horário |
| `*cropman*.csv/xlsx` | análises de solo |
| `ndvi_metadata.csv` | NDVI por talhão e data |
| `*ekos*.csv/xlsx` | produtividade (camada de colheita, agregada por talhão) |
| `traps_events.csv` + imagens | diagnósticos de praga com bounding boxes |

As colunas são reconhecidas por apelidos (ver `MAPAS` em `backend/app/services/ingestao.py`).
Se algum arquivo tiver nomes de coluna diferentes, basta acrescentar o apelido no mapa.
`python -m scripts.seed_farmlab --demo` força os dados sintéticos. O seed pode ser rodado de novo sem duplicar.

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
