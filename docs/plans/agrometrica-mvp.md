# Plano: AgroMétrica MVP

Spec: docs/spec.md (binding). Banco: MySQL 8.

## Global Constraints
- Routers só recebem/devolvem; regra de negócio em services; sem pandas/cv2 em routers.
- Todas as rotas sob /api. Erros `{"detail": ...}`; 400/401/403/404.
- JSON e Python em snake_case; componentes React em PascalCase.
- Testes rodam em SQLite (DATABASE_URL override em conftest) para não exigir MySQL no CI;
  código ORM deve ser portátil MySQL/SQLite (upsert via helper por dialeto).
- Limiares NDVI/hídrico em `backend/app/core/regras.toml`, nunca fixos no código.
- Commits: feat:/fix:/docs:/refactor:/test:, cada um termina com a linha Co-Authored-By.

## Interfaces
- Task 2 produz `app.core.database.Base, get_db, SessionLocal, engine`; `app.core.security.hash_senha, verificar_senha, criar_token, get_current_user, require_role(*perfis)`; `app.core.config.settings`. Consumidos por 3–9.
- Task 2 produz modelos em `app.models` (um arquivo por tabela; `app.models.__init__` importa todos). Consumidos por 3–10.
- Task 4 produz `services.ingestao.importar(db, tipo, arquivo_bytes, nome, usuario_id) -> dict`. Consumido por 3 (seed) e 4 (router).
- Task 5 produz `services.imagem.processar_imagem(db, imagem_id)`, `calcular_vari(bgr)`, `estatisticas_ndvi_geotiff(path)`.
- Task 6 produz `services.diagnostico.rodar(db, talhao_id) -> list[Diagnostico]`, `services.alertas.gerar_para(db, diag)`, `services.prescricao.sugerir(db, diag)`.
- Tests fixtures (`tests/conftest.py`): `client`, `db`, `admin_token`, `agronomo_token`, `auth(token)` header helper.

## Task 1: Scaffold do repositório
Arquivos: `.gitignore`, `docker-compose.yml` (mysql:8, 3306, volume dbdata), `.env.example`, `README.md`, `storage/.gitkeep`, `backend/requirements.txt`, `backend/pyproject.toml` (ruff: line-length 110), `.github/workflows/ci.yml` (dois jobs conforme spec).
Verificação: `docker compose config` → Expected: config válida sem erro.

## Task 2: Núcleo do backend (config, db, security, modelos, Alembic)
- `core/config.py` (pydantic-settings, lê `.env` da raiz ou backend; `regras.toml` carregado em `settings.regras`).
- `core/database.py`, `core/security.py` (passlib bcrypt, python-jose HS256, OAuth2 bearer; 401 sem token, 403 sem perfil).
- `models/*.py` para as 13 tabelas da spec §5 (geometria como Text WKT).
- `main.py` com CORS e `/api/health`.
- Alembic em `backend/migrations`, env.py lendo settings.DATABASE_URL e `Base.metadata`; migração inicial autogerada contra MySQL.
Testes: `tests/test_health.py` (GET /api/health → 200).
Expected: `pytest -q` → 1 passed; `alembic upgrade head` contra MySQL cria 13 tabelas.

## Task 3: Auth + usuários + talhões + clima (Sprint 0/1)
- routers auth (`POST /auth/login`, `GET /auth/me`), usuarios (CRUD ADMIN), talhoes (lista paginada `page,size,sort,busca,deficit_min,sistema`; detalhe com últimas métricas; `/metricas?de&ate`; `/solo` com classificação), clima (`/clima?de&ate&agregacao=dia`).
- schemas Pydantic XCreate/XUpdate/XOut.
Testes (escritos antes): `test_auth.py` (login ok, senha errada 401, /me sem token 401, agrônomo em /usuarios 403, admin 200); `test_talhoes.py` (paginação: 4 talhões, size=2 → total 4, 2 itens, page 2 → 2 itens; busca filtra; 404).
Expected: todos passam.

## Task 4: Ingestão de CSV (Sprint 2)
- `services/ingestao.py`: mapas de colunas por tipo (CLIMA, SOLO, NDVI, COLHEITA), com aliases (nomes Metos/Cropman/OneSoil/EKOS e nomes canônicos); leitura `sep=None, engine="python", decimal=","`, datas `dayfirst=True`; coluna obrigatória faltando → `HTTPException(400)` levantada como `ColunaObrigatoriaError` e convertida no router; linha inválida → erros[]; upsert por chave única.
- `routers/uploads.py` `POST /uploads/{tipo}`, grava registro em `uploads`.
Testes: `test_uploads.py` — CSV Metos válido com `;` e vírgula decimal → linhas_ok=N, linhas_erro=0; CSV com uma linha inválida → linhas_erro=1, demais ok; faltando coluna → 400; reenviar mesmo CSV → sem duplicar (count igual).
Expected: todos passam.

## Task 5: Imagens (Sprint 3)
- `services/storage.py` (salvar em STORAGE_DIR/<subdir>/uuid.ext), `services/imagem.py` (VARI com colormap; GeoTIFF: banda1 mascarada por banda3 → upsert metricas_talhao).
- `routers/imagens.py` `POST /imagens` → 202 + BackgroundTasks; `GET /imagens/{id}`; `GET /arquivos/{path}` para servir storage.
Testes: `test_imagem.py` — `calcular_vari` numa imagem sintética verde tem média > 0 e gera arquivo; GeoTIFF sintético (rasterio, 2 bandas... banda3 máscara) → média/min/max corretos considerando só pixels mascarados; POST /imagens → 202 e status final PROCESSADO.
Expected: passam.

## Task 6: Diagnóstico, prescrição e alertas (Sprint 4)
- `core/regras.toml`: `[ndvi] queda_media=0.15 queda_alta=0.30`, `[hidrico] janela_dias=7 limite_mm=-25`, `[solo] ph_min=5.0 v_min=50 p_min=... k_min=...`, `[janela_aplicacao] vento_max=10 umidade_min=55 temp_max=30 horas_sem_chuva=2`.
- `services/diagnostico.py`: `classificar_praga(contagem, praga)`, `avaliar_ndvi`, `avaliar_hidrico`, `avaliar_solo`, `rodar(db, talhao_id)`.
- `services/prescricao.py`: dose média; janela a partir de leituras_clima futuras/recentes.
- `services/alertas.py`: MEDIA/ALTA cria alerta.
- routers diagnosticos, pragas, produtos (CRUD, escrita ADMIN), prescricoes (PATCH AGRONOMO+), alertas.
Testes: `test_diagnostico.py` — uma por regra (armadilha dano/controle/alerta; NDVI 20%→MEDIA, 35%→ALTA, 10%→nada; hídrico −30→HIDRICO MEDIA; pH 4.8→NUTRICIONAL); `test_prescricao.py` (dose média; janela respeita condições; nasce SUGERIDA); `test_alertas.py` (BAIXA não gera; ALTA gera); PATCH prescricao por agrônomo → APROVADA; CRUD produtos admin ok, agrônomo 403.
Expected: todos passam.

## Task 7: Dashboard e comparativo (Sprint 5, backend)
- `GET /dashboard/resumo`: cards (talhões, área total, alertas abertos, diagnósticos 30d), ndvi_por_talhao (séries), severidade_por_talhao, geometrias.
- `GET /comparativo?a&b`: por talhão ndvi, produtividade, contagem de pragas por data, clima diário, eventos (diagnósticos).
Testes: `test_dashboard.py` — resumo tem chaves e contagens; comparativo 404 com id inválido e 200 com séries.
Expected: passam.

## Task 8: Seed FarmLab
- `scripts/seed_farmlab.py --data-dir data/raw/farmlab [--demo]`: cria admin (`admin@agrometrica.local` / `admin123`) e agrônomo; talhões de fields.csv; pragas; clima via ingestão; solo; NDVI; colheita agregada; traps_events → imagens ARMADILHA + diagnósticos com bboxes em detalhes.
- `--demo` (ou arquivos ausentes): gera dados sintéticos determinísticos (4 talhões, 49 datas NDVI, clima horário, solo, armadilhas com bboxes, produtos e vínculos).
Teste: `test_seed.py` roda seed demo em SQLite → 4 talhões, 49 datas NDVI por talhão, ≥1 diagnóstico com bboxes.
Expected: passa.

## Task 9: Frontend base
- Vite React, Tailwind v4 plugin, proxy /api, ESLint.
- `api/client.js` (axios baseURL /api, token do localStorage, 401 → logout), `api/*.js` por recurso.
- `context/AuthContext.jsx`, `routes/AppRoutes.jsx`, `PrivateRoute.jsx`, `RoleRoute.jsx`, layout com menu.
- Páginas Login, Talhoes (DataTable server-side), Usuarios.
Expected: `npm run lint` e `npm run build` sem erro.

## Task 10: Frontend completo
- Dashboard (AlertBar 60s, cards, gráfico NDVI, MapaTalhoes Leaflet por severidade), TalhaoDetalhe (abas; `?diagnostico=`), Upload (Dropzone), Diagnosticos, DiagnosticoDetalhe (ImageCompare, BBoxCanvas, prescrições com aprovar + aviso técnico), Produtos/Pragas CRUD com modal, Comparativo.
- Rótulo "índice RGB (VARI)" para imagens RGB.
Expected: `npm run lint` e `npm run build` sem erro; smoke manual com API + seed demo.

## Task 11: Integração MySQL ponta a ponta
- `docker compose up -d`, `alembic upgrade head`, `python scripts/seed_farmlab.py --demo`, uvicorn, requisições via httpx: login, /talhoes (4), /alertas.
Expected: todas 200 e dados presentes.
