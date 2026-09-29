# Especificação: AgroMétrica

Banco escolhido: **MySQL 8** (decisão do usuário). Onde a especificação original
usava PostgreSQL/PostGIS, vale a variante (MySQL): `pymysql`, sem `geoalchemy2`,
geometria dos talhões em texto WKT, imagem `mysql:8`, porta 3306.

## 1. Pré-requisitos
Python 3.12, Node.js 20 LTS, Git, Docker Desktop.
Extensões VSCode: Python, Pylance, Ruff, ESLint, Prettier, Docker, Thunder Client, Rainbow CSV.

## 2. Criação
- Raiz: `backend/`, `frontend/`, `storage/`, `.gitignore`, `docker-compose.yml`, `.env.example`, `README.md`.
- Backend: venv, `pip install -r requirements.txt`, `alembic init migrations`, `uvicorn app.main:app --reload` (docs em http://localhost:8000/docs).
- Frontend: Vite + React; deps `react-router-dom @tanstack/react-query @tanstack/react-table axios recharts react-dropzone leaflet react-leaflet`; dev `tailwindcss @tailwindcss/vite eslint prettier`. Roda em http://localhost:5173.
- Banco: `docker compose up -d`.

## 3. Configuração
requirements.txt: fastapi, uvicorn[standard], sqlalchemy>=2.0, alembic, pymysql, pydantic-settings,
python-jose[cryptography], passlib[bcrypt], python-multipart, pandas, openpyxl,
opencv-python-headless, rasterio, numpy, pytest, httpx, ruff.

docker-compose: serviço `db` com `mysql:8`, usuário/senha `agro`, banco `agrometrica`, porta 3306, volume `dbdata`.

.env.example:
```
DATABASE_URL=mysql+pymysql://agro:agro@localhost:3306/agrometrica
JWT_SECRET=troque-isto
JWT_EXPIRES_MIN=480
STORAGE_DIR=../storage
CORS_ORIGINS=http://localhost:5173
```
vite.config.js: `server: { proxy: { '/api': 'http://localhost:8000' } }`. Todos os routers com prefixo `/api`.

.gitignore: `.venv/ node_modules/ .env storage/* !storage/.gitkeep __pycache__/ dist/ data/raw/`

CI (`.github/workflows/ci.yml`): backend (python 3.12 → pip install → ruff check . → pytest);
frontend (node 20 → npm ci → npm run lint → npm run build).

## 4. Estrutura
```
backend/app/
  main.py, core/config.py, core/database.py, core/security.py
  models/ (1 arquivo por tabela), schemas/ (XCreate, XUpdate, XOut)
  routers/ auth, usuarios, talhoes, uploads, imagens, diagnosticos, pragas, produtos, prescricoes, alertas, dashboard
  services/ ingestao, imagem, diagnostico, prescricao, alertas, storage
backend/scripts/seed_farmlab.py
backend/tests/
frontend/src/
  api/client.js, api/*.js
  routes/ AppRoutes.jsx, PrivateRoute.jsx, RoleRoute.jsx
  pages/ Login, Dashboard, Talhoes, TalhaoDetalhe, Upload, Diagnosticos, DiagnosticoDetalhe, Produtos, Pragas, Comparativo, Usuarios
  components/ AlertBar, DataTable, Dropzone, ImageCompare, BBoxCanvas, MapaTalhoes, charts/
  context/AuthContext.jsx
```
Camadas: router só recebe/devolve; service tem a regra; model é o banco. Sem Pandas/OpenCV em router.

## 5. Banco
| Tabela | Colunas |
|---|---|
| usuarios | id, nome varchar(100), email unique, senha_hash, perfil enum(ADMIN, AGRONOMO), ativo, criado_em |
| talhoes | id, nome, area_ha numeric(8,2), cultura, sistema enum(AGRO_4_0, CONVENCIONAL), finalidade enum(GRAO, SILAGEM), geometria (texto WKT) |
| leituras_clima | id, data_hora unique, temp_min, temp_med, temp_max, chuva_mm, umidade_med, vento_kmh, radiacao, etp_mm |
| leituras_solo | id, talhao_id FK, zona, ponto, lat, lon, data_coleta, ph, mo, ctc, p, k, ca, mg, s, b, zn, mn, cu, v_pct |
| metricas_talhao | id, talhao_id FK, data, ndvi_medio, ndvi_min, ndvi_max, balanco_hidrico_mm, produtividade_kg_ha; unique(talhao_id, data) |
| imagens | id, talhao_id FK, tipo enum(FOLHA, ORTOMOSAICO, NDVI_GEOTIFF, ARMADILHA), caminho, caminho_processado, data_captura, status enum(PENDENTE, PROCESSANDO, PROCESSADO, ERRO), enviado_por FK |
| pragas | id, nome, nome_cientifico, cultura, limiar_alerta, limiar_controle, limiar_dano |
| produtos | id, nome_comercial, ingrediente_ativo, classe enum(INSETICIDA, FUNGICIDA, HERBICIDA, FERTILIZANTE, CORRETIVO), dose_min, dose_max, unidade, carencia_dias, registro_mapa |
| praga_produto | praga_id FK, produto_id FK (PK composta) |
| diagnosticos | id, imagem_id FK null, talhao_id FK, praga_id FK null, tipo enum(PRAGA, VIGOR, NUTRICIONAL, HIDRICO), severidade enum(BAIXA, MEDIA, ALTA), confianca, detalhes JSON, criado_em |
| prescricoes | id, diagnostico_id FK, produto_id FK, dose, unidade, janela_inicio, janela_fim, status enum(SUGERIDA, APROVADA, APLICADA, DESCARTADA), aprovado_por FK |
| alertas | id, talhao_id FK, diagnostico_id FK, severidade, mensagem, lido, criado_em |
| uploads | id, usuario_id FK, nome_arquivo, tipo enum(CLIMA, SOLO, NDVI, COLHEITA), linhas_ok, linhas_erro, erros JSON, criado_em |

Toda alteração de tabela via Alembic (`revision --autogenerate` + `upgrade head`).

## 6. API (prefixo /api)
| Rota | Perfil | Descrição |
|---|---|---|
| POST /auth/login | público | {email, senha} → {access_token, usuario} |
| GET /auth/me | logado | usuário atual |
| CRUD /usuarios | ADMIN | |
| GET /talhoes?page&size&sort&busca&deficit_min | logado | {items, total, page, size} |
| GET /talhoes/{id} | logado | detalhe + últimas métricas |
| GET /talhoes/{id}/metricas?de&ate | logado | série temporal |
| GET /talhoes/{id}/solo | logado | pontos com classificação |
| GET /clima?de&ate&agregacao=dia | logado | clima agregado por dia |
| POST /uploads/{tipo} | logado | multipart → {linhas_ok, linhas_erro, erros[]} |
| POST /imagens | logado | multipart (arquivo, talhao_id, tipo) → 202, processa em background |
| GET /imagens/{id} | logado | status e caminhos |
| GET /diagnosticos?talhao_id&severidade | logado | lista |
| GET /diagnosticos/{id} | logado | detalhe com bboxes e prescrições |
| POST /diagnosticos/rodar/{talhao_id} | AGRONOMO+ | motor de regras |
| CRUD /pragas, /produtos | escrita ADMIN | catálogo |
| PATCH /prescricoes/{id} | AGRONOMO+ | aprovar/descartar |
| GET /alertas?lido=false | logado | barra de alertas |
| PATCH /alertas/{id}/lido | logado | marca lido |
| GET /dashboard/resumo | logado | cards, NDVI por talhão, contagem de alertas |
| GET /comparativo?a&b | logado | séries lado a lado |

Erro: `{"detail": "..."}`; 400 validação, 401 sem token, 403 sem permissão, 404 não encontrado.

## 7. Regras de negócio
**Ingestão**: `sep=None, engine="python"`; `decimal=","`; `dayfirst=True`; mapa de colunas por tipo; coluna obrigatória faltando → 400; linha inválida vai para erros[] sem derrubar o lote; duplicados ignorados (upsert).

**Imagem**: GeoTIFF OneSoil: banda 1 com rasterio, máscara banda 3, média/mín/máx → metricas_talhao. Foto RGB: VARI = (G−R)/(G+R−B) ou ExG = 2G−R−B, `cv2.applyColorMap`, salva em caminho_processado. Interface mostra "índice RGB (VARI)", nunca "NDVI".

**Diagnóstico v1**:
| Regra | Resultado |
|---|---|
| armadilha ≥ limiar_dano | PRAGA, ALTA |
| ≥ limiar_controle | PRAGA, MEDIA |
| ≥ limiar_alerta | PRAGA, BAIXA |
| NDVI caiu >15% entre duas leituras | VIGOR, MEDIA (>30%: ALTA) |
| balanço hídrico 7 dias < −25 mm | HIDRICO, MEDIA |
| pH < 5,0 ou V% < 50 ou K/P abaixo da faixa | NUTRICIONAL, BAIXA ou MEDIA |
Limiares de NDVI e balanço hídrico em arquivo de configuração.

**Prescrição**: PRAGA → produtos em praga_produto, dose média (min+max)/2. Janela: vento < 10 km/h, umidade > 55%, temp < 30 °C, sem chuva nas 2 h seguintes. Nasce SUGERIDA; só agrônomo aprova. Aviso na interface: recomendação a validar por responsável técnico.

**Alertas**: diagnóstico MEDIA/ALTA cria alerta. ALTA vermelho, MEDIA amarelo, BAIXA não gera.

**Seed**: admin padrão + 4 talhões (fields.csv); pragas (pest_details.csv), clima (Metos), solo (Cropman), NDVI (ndvi_metadata.csv), produtividade (EKOS, agregada por talhão); armadilhas (traps_events.csv) viram diagnósticos com bboxes.

## 8. Frontend
| Rota | Página | Componentes |
|---|---|---|
| /login | Login | token no AuthContext e localStorage |
| / | Dashboard | AlertBar, cards, linhas NDVI por talhão, MapaTalhoes por severidade |
| /talhoes | Talhoes | DataTable paginação servidor; filtros busca, sistema, déficit |
| /talhoes/:id | TalhaoDetalhe | abas Métricas, Solo, Clima, Diagnósticos; ?diagnostico=ID |
| /upload | Upload | Dropzone + tipo + relatório |
| /diagnosticos/:id | DiagnosticoDetalhe | ImageCompare, BBoxCanvas, prescrições com aprovar |
| /produtos, /pragas | CRUD | DataTable + modal (edição só ADMIN) |
| /comparativo | Comparativo | 4.0 × Convencional: NDVI, produtividade, pragas, clima, eventos |
| /usuarios | Usuarios | só ADMIN |

TanStack Query em toda chamada; AlertBar refetchInterval 60 s; clique no alerta → /talhoes/{talhao_id}?diagnostico={id}; BBoxCanvas com coords 0–1 escaladas.

## 9. Convenções
Branches main/dev/feat/*; commits feat:/fix:/docs:/refactor:/test:; snake_case Python e JSON; PascalCase componentes.
Testes mínimos: login, upload CSV válido e inválido, cada regra de diagnóstico, paginação de talhões.

## 10. Pronto por sprint
0: React lista os 4 talhões da API. 1: login; Agrônomo 403 em /usuarios; CI passa.
2: CSV Metos sobe e aparece em gráfico. 3: 49 datas NDVI; gráfico 4.0 × convencional; foto RGB gera VARI.
4: armadilha com bboxes e prescrição sugerida; CRUD produtos. 5: alerta vermelho leva ao talhão com diagnóstico; Comparativo pronto.
