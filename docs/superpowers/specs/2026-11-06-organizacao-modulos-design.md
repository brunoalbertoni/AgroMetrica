# Organização do código por módulo

Data: 2026-11-06 · Status: aprovado em conversa

## Objetivo

Achar o código de um assunto (talhões, diagnósticos, catálogo...) abrindo uma pasta só, com nomes
padronizados. **Sem mudar comportamento**: só caminhos, nomes e imports.

## Regras

- Módulos no plural, em português. Dentro de cada módulo do backend: `router.py`, `service.py`,
  `schemas.py` (o que existir). Catálogo tem dois routers: `router_pragas.py` e `router_produtos.py`.
- Utilitários usados por vários módulos ficam em `comum/` (backend) e `compartilhado/` (frontend).
- `core/` e `models/` ficam onde estão (o Alembic importa `app.models`).
- Comandos não mudam: `uvicorn app.main:app`, `python -m scripts.seed_farmlab`, `npm run dev`.

## Backend (`backend/app/`)

| Destino | Origem |
|---|---|
| `modulos/talhoes/{router,service,schemas}` | routers/talhoes, services/talhoes, schemas/talhao |
| `modulos/diagnosticos/{router,service,schemas}` | routers/diagnosticos, services/diagnostico, schemas/diagnostico (BBox, DiagnosticoOut, DiagnosticoDetalhe, ArmadilhaIn) |
| `modulos/alertas/{router,service,schemas}` | routers/alertas, services/alertas, AlertaOut |
| `modulos/prescricoes/{router,service,schemas}` | routers/prescricoes, services/prescricao, PrescricaoOut/Patch |
| `modulos/catalogo/{router_pragas,router_produtos,service,schemas}` | routers/pragas e produtos, services/catalogo, schemas/catalogo |
| `modulos/imagens/{router,service}` | routers/imagens, services/imagem |
| `modulos/uploads/{router,ingestao}` | routers/uploads, services/ingestao |
| `modulos/clima/service` | services/clima |
| `modulos/dashboard/{router,service}` | routers/dashboard, services/dashboard |
| `modulos/usuarios/{router,router_auth,service,schemas}` | routers/usuarios e auth, services/usuarios, schemas/usuario |
| `modulos/assistente/{router,service,tools}` | routers/assistente, services/assistente, services/assistente_tools |
| `comum/{geo,storage,upsert,exclusao}` | services/geo, storage, upsert, exclusao |

Testes: renomear `test_diagnostico`→`test_diagnosticos`, `test_imagem`→`test_imagens`,
`test_prescricao`→`test_prescricoes`.

## Frontend (`frontend/src/`)

- `app/`: AppRoutes, Layout, PrivateRoute, RoleRoute.
- `compartilhado/`: api/client.js, ui.jsx, DataTable, charts/, lib/format.js, lib/geo.js.
- `modulos/<assunto>/`: `paginas/`, `componentes/`, `api.js`. Assuntos: talhoes, diagnosticos,
  alertas, catalogo, uploads, dashboard, auth, usuarios, assistente.

## Verificação

Branch `refactor/organizacao-modulos`; `git mv` para preservar histórico. Backend: `ruff check` e
`pytest` (mesmos testes, mesmas contagens de antes). Frontend: `eslint` e `build`. README ganha o
mapa de pastas.

## Fora de escopo

Quebrar `TalhaoDetalhe.jsx` e `seed_farmlab.py`; mudar rotas da API, banco ou lógica.

## Estrutura final (decidida durante a execução)

O usuário pediu organização **por camada, com pasta de módulo dentro**, em vez de `modulos/<assunto>/...`:

- Backend: `controllers/<m>/<m>Controller.py`, `services/<m>/<m>Service.py`, `schemas/<m>/<m>Schemas.py`.
  O catálogo foi dividido em `pragas` e `produtos` (controller, service e schemas de cada). O assistente
  tem `services/assistente/assistenteService.py` e `assistenteTools.py`; uploads tem `ingestaoService.py`.
- Frontend: `api/<m>/<M>Api.js`, `paginas/<m>/`, `componentes/<m>/`, `stores/<m>/`, além de `app/` e `compartilhado/`.
- Mesmo comportamento de antes: `ruff` limpo, 113 testes do backend passando (as 2 falhas de `test_seed` já existiam), `eslint` sem erros e `build` ok.
