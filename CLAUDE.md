# Sentinela Pix — Especificação de execução

Detecção de fraude em Pix em tempo real + console de analistas. Dados 100% sintéticos.

## REGRAS DE EXECUÇÃO (obrigatórias)
- NÃO faça perguntas. NÃO proponha alternativas. Todas as decisões já estão aqui; siga literalmente.
- Não pesquise nem compare bibliotecas. Use SOMENTE as dependências listadas.
- Sem autenticação, sem migrations (use `Base.metadata.create_all`), sem Kubernetes, sem shadcn, sem libs de gráfico.
- Use a versão estável mais recente de cada dependência; não fixe versões menores a menos que a instalação falhe.
- Rode os testes UMA vez ao final de cada fase; corrija só o que falhar.
- Se algo travar por mais de ~5 minutos, simplifique e siga.
- Ao final de cada fase: `git add -A && git commit -m "fase N: <resumo>" && git push`.
- Comentários e docstrings curtos. Nada de documentação longa além do README da Fase 6.
- Textos de UI e mensagens em português; nomes de código em português conforme abaixo.

## SESSÕES E RETOMADA (obrigatório)
O trabalho é dividido em 4 sessões curtas para não acumular contexto. Cada sessão executa SOMENTE o seu bloco de fases e para:
- Sessão A: fases 1–2
- Sessão B: fases 3–4
- Sessão C: fases 5–6
- Sessão D: fases 7–8

Ao iniciar qualquer sessão:
1. Rode `git log --oneline | grep -E "^[0-9a-f]+ fase [0-9]+" | head -5` para descobrir a última fase concluída. A próxima fase pendente é a seguinte a ela (se não houver commits, comece na fase 1).
2. Não explore o código de fases anteriores além do estritamente necessário para a fase atual; confie na especificação deste arquivo para as interfaces (nomes de funções, tabelas, endpoints).
3. Execute as fases pendentes do bloco da sessão atual, com commit e push ao final de cada uma.
4. Ao terminar o bloco, responda apenas: `Bloco concluído. Próxima sessão: <letra> (fases X–Y).` e PARE.

Se a sessão for interrompida no meio de uma fase (limite de uso, erro), a próxima sessão retoma a partir da fase pendente indicada pelo `git log`, descartando alterações não commitadas com `git stash` apenas se elas impedirem os testes de passar.

## ECONOMIA DE TOKENS (obrigatório)
- Silencie comandos ruidosos: `pip install -q ... 2>&1 | tail -5`, `npm ci --silent --no-audit --no-fund 2>&1 | tail -5`, `npx create-next-app ... 2>&1 | tail -5`, `npm run build 2>&1 | tail -30`, `pytest -q 2>&1 | tail -30`, `docker compose up -d --build 2>&1 | tail -10`.
- Em falha, leia só as linhas finais do erro (`| tail -40`), nunca o log inteiro.
- NÃO releia arquivos que você acabou de escrever. NÃO abra package-lock.json, node_modules, .next, arquivos gerados ou artefatos.
- NÃO liste diretórios inteiros recursivamente; a estrutura está definida acima.
- Escreva cada arquivo de uma vez, completo; prefira editar trechos pequenos a reescrever o arquivo.
- Respostas entre passos: no máximo 1 linha. Sem resumos de progresso, sem explicar o código.
- Não rode o servidor de desenvolvimento em primeiro plano; valide com testes e `npm run build`.
- Se Docker não estiver disponível, não tente instalá-lo: valide com testes (SQLite + fakeredis) e siga.

## ESTRUTURA (crie exatamente)
```
sentinela-pix/
  CLAUDE.md
  README.md
  Makefile
  docker-compose.yml
  .env.example
  .gitignore
  .github/workflows/ci.yml
  backend/
    Dockerfile
    requirements.txt
    pyproject.toml            # config de pytest e ruff
    artifacts/.gitkeep        # modelo treinado (conteúdo no .gitignore)
    sentinela/
      __init__.py
      config.py               # pydantic-settings
      db.py                   # engine, SessionLocal, modelos ORM, init_db()
      gerador.py
      features.py
      grafo.py
      treino.py
      modelo.py
      regras.py
      decisao.py
      produtor.py
      consumer.py
      seed.py
      llm.py
      api/
        __init__.py
        main.py
        schemas.py
    tests/
      conftest.py
      test_gerador.py
      test_features.py
      test_regras.py
      test_modelo.py
      test_api.py
  frontend/                   # Next.js (create-next-app)
```

## STACK
- Backend (`backend/requirements.txt`): fastapi, uvicorn[standard], sqlalchemy, psycopg[binary], pydantic-settings, redis, numpy, pandas, lightgbm, shap, networkx, anthropic, httpx, pytest, fakeredis, ruff.
- Frontend: Next.js 15 (App Router, TypeScript, Tailwind, src/), @tanstack/react-query. Criar com `npx create-next-app@latest frontend --ts --tailwind --eslint --app --src-dir --use-npm --no-import-alias` (aceite padrões se houver prompt).
- Infra: Postgres 16, Redis 7, Docker Compose.

## CONFIG (`config.py`, lido de env / `.env`)
```
DATABASE_URL=postgresql+psycopg://sentinela:sentinela@localhost:5432/sentinela
REDIS_URL=redis://localhost:6379/0
STREAM_NAME=pix:tx
CONSUMER_GROUP=decisor
MODEL_PATH=artifacts/modelo.txt
MODEL_META_PATH=artifacts/modelo_meta.json
ANTHROPIC_API_KEY=
LLM_MODEL=claude-haiku-5-5
CORS_ORIGINS=http://localhost:3000
```

## BANCO (`db.py`, SQLAlchemy 2 estilo `Mapped`)
Use `sqlalchemy.JSON` (não JSONB) para funcionar também com SQLite nos testes.
- `contas`: id str PK, criada_em datetime, tipo str (`normal`|`laranja`)
- `transacoes`: id str PK (uuid4 str), ts datetime (index), origem str (index), destino str (index), valor float, dispositivo str, is_fraude bool, padrao str|null
- `decisoes`: transacao_id str PK FK, score float, decisao str (index), motivos JSON, features JSON, modelo_versao str, latencia_ms float, criado_em datetime
- `rotulos`: transacao_id str PK FK, rotulo str (`fraude`|`legitima`), analista str, criado_em datetime
- `init_db()` chama `create_all`.

## GERADOR (`gerador.py`)
`gerar_contas(n=2000, seed=42)` e `gerar_transacoes(contas, inicio, dias, seed=42) -> list[dict]` ordenadas por ts.
- 5% das contas são `laranja`. Cada conta tem `criada_em` entre 1 e 1500 dias antes de `inicio` (laranjas: 1 a 30 dias). Cada conta normal tem 1–2 dispositivos (`dev-<uuid8>`) e 5–15 contatos fixos (outras contas normais).
- Normal: cada conta faz Poisson(3)/dia; valor lognormal(mean=4.5, sigma=1.0) limitado a [1, 20000], arredondado a 2 casas; hora com pesos maiores entre 8h e 22h; destino = contato aleatório; dispositivo habitual.
- Fraudes (~2% do total de transações, `is_fraude=True`):
  - `falso_parente`: vítima normal envia 1–3 tx em 30 min para um destino novo (laranja), valor uniforme 500–3000, dispositivo habitual.
  - `conta_laranja`: 5–20 vítimas distintas enviam para a MESMA laranja em até 1h (valor 200–2000); 10–40 min depois a laranja repassa 90% do total recebido para outra laranja (cadeia de 2–3 saltos; repasses também `is_fraude=True`).
  - `account_takeover`: entre 0h e 5h, dispositivo NOVO, 3–8 tx em até 20 min, valores crescentes 300→5000, destinos novos (laranjas).
- Cada dict: `id, ts, origem, destino, valor, dispositivo, is_fraude, padrao`.

## FEATURES (`features.py`) — mesma função no batch e no online
Lista ordenada `FEATURES` e `ROTULOS_PT` (nome legível em PT-BR para cada uma):
| feature | definição |
|---|---|
| valor | valor da tx |
| log_valor | log1p(valor) |
| hora | hora local 0–23 |
| madrugada | 1 se 0 ≤ hora < 6 |
| qtd_origem_5m | nº de tx da origem nos 5 min anteriores |
| qtd_origem_1h | nº de tx da origem na 1h anterior |
| soma_origem_1h | soma de valores da origem na 1h anterior |
| destinatario_novo | 1 se origem nunca enviou ao destino |
| dispositivo_novo | 1 se dispositivo nunca usado pela origem |
| idade_conta_destino_dias | dias entre criada_em do destino e ts |
| origens_distintas_destino_1h | nº de origens distintas que enviaram ao destino na 1h anterior |
| razao_valor_media | valor / média das últimas 30 tx da origem (1.0 se não houver) |
| grau_destino | nº de contrapartes distintas do destino (do grafo) |
| dist_fraude_conhecida | menor distância (não-direcionada, até 3) do destino a uma conta de fraude conhecida; 4 se nenhuma |

- Interface `Estado` (Protocol) com métodos usados pelas features; duas implementações: `EstadoMemoria` (dicts/deques, para batch) e `EstadoRedis` (sorted sets `orig:{id}:ts` com score=epoch, sets `orig:{id}:dests`, `orig:{id}:devs`, sorted set `dest:{id}:origs`, list `orig:{id}:vals` LTRIM 30, hash `grafo:{id}`; janelas via ZRANGEBYSCORE + ZREMRANGEBYSCORE para expirar > 1h).
- `calcular_features(tx, estado, contas_criada_em) -> dict` lê o estado ANTES de `estado.registrar(tx)`.
- Features de grafo vêm do estado (`grafo:{id}` no Redis / dict em memória), preenchidas por `grafo.py`.

## GRAFO (`grafo.py`)
- `construir(transacoes) -> nx.Graph` (não-direcionado, aresta origem–destino).
- `calcular_metricas(G, contas_fraude: set) -> dict[conta, {grau_destino, dist_fraude_conhecida}]` usando `multi_source_dijkstra_path_length` com cutoff=3.
- Contas de fraude conhecidas = destinos de tx `is_fraude` na janela de TREINO + contas rotuladas `fraude` no console (evita vazamento).
- `atualizar_redis(metricas, redis)` grava hashes `grafo:{id}`.
- `subgrafo_2_saltos(G, conta, max_nos=40) -> {nodes:[{id,tipo,fraude_conhecida}], edges:[{source,target,qtd,valor_total}]}`.

## TREINO (`treino.py`, `python -m sentinela.treino`)
- Entrada: transações do banco ordenadas por ts. Split temporal 80/20.
- Grafo e contas de fraude a partir dos primeiros 80%. Features via `EstadoMemoria` percorrendo em ordem.
- LightGBM: `objective=binary, n_estimators=300, learning_rate=0.05, num_leaves=31, scale_pos_weight=neg/pos, random_state=42`.
- Métricas no teste: PR-AUC (average_precision via numpy, sem sklearn), precisão e recall nos limiares 0.4 e 0.85, nº de amostras e taxa de fraude.
- Salva `booster.save_model(MODEL_PATH)` e `modelo_meta.json` = `{versao: "v<timestamp>", features, metricas, treinado_em}`.
- Implemente average_precision manualmente (ordenar por score, acumular precisão nos positivos).

## MODELO (`modelo.py`)
Classe `Modelo` singleton: `carregar()`, `pontuar(features: dict) -> float`, `explicar(features) -> list[{feature, rotulo, valor, impacto}]` (shap.TreeExplainer, top 5 por |impacto|, impacto arredondado a 4 casas).

## REGRAS (`regras.py`)
`decidir(score, f) -> (decisao, regras_disparadas: list[str])`:
1. `BLOQUEAR` se score ≥ 0.85, ou (dispositivo_novo and madrugada and valor > 2000).
2. `REVISAR` se score ≥ 0.40, ou origens_distintas_destino_1h ≥ 5, ou (destinatario_novo and razao_valor_media ≥ 10).
3. Senão `APROVAR`.
Regras disparadas entram em `motivos` como `{feature: "regra", rotulo: "<texto PT-BR>", valor: null, impacto: null}` antes dos motivos SHAP.

## DECISÃO (`decisao.py`)
`processar(tx, estado, sessao) -> dict`: mede latência com `time.perf_counter`, calcula features, pontua, explica, aplica regras, registra no estado, persiste transação+decisão com idempotência (se `transacao_id` já existe em `decisoes`, retorna a existente sem reprocessar). Retorna o payload de resposta de `/decisao`.

## STREAMING
- `produtor.py` (`python -m sentinela.produtor --tps 10 --minutos 10`): gera transações "ao vivo" (ts = agora) com o mesmo gerador usando as contas existentes no banco, publica via `XADD pix:tx * dados <json>`.
- `consumer.py` (`python -m sentinela.consumer`): cria o grupo se não existir (`MKSTREAM`), `XREADGROUP` em lote de 100, block 2000 ms, chama `processar`, `XACK` após commit. A cada 500 mensagens recalcula o grafo (últimas 24h do banco + contas rotuladas fraude) e atualiza Redis. Log de 1 linha a cada 100 msgs com tps e latência média.

## SEED (`seed.py`, `python -m sentinela.seed`)
1. `init_db()`; limpa tabelas e `FLUSHDB` no Redis.
2. Gera 2000 contas e 30 dias de histórico terminando agora; insere em lote (`bulk_insert_mappings` ou `insert()` com listas de 5000).
3. Roda o treino.
4. Popula o `EstadoRedis` com os últimos 2 dias (para as janelas e conjuntos) e o grafo.
5. Processa as últimas 3000 transações do histórico via `processar` para que o console já abra com casos.
Imprime métricas do modelo ao final.

## API (`api/main.py`)
CORS para `CORS_ORIGINS`. `init_db()` e `Modelo.carregar()` no lifespan (se não houver modelo, endpoints de decisão retornam 503 com mensagem "rode make seed").
- `GET /health` → `{status: "ok", modelo_versao}`
- `POST /decisao` body `{id?: str, ts?: datetime, origem, destino, valor, dispositivo}` → `{transacao_id, score, decisao, motivos, latencia_ms, modelo_versao}`
- `GET /casos?decisao=REVISAR|BLOQUEAR&pendentes=true&limit=50&offset=0` → `{itens:[{transacao_id, ts, origem, destino, valor, score, decisao, rotulo|null}], total}` ordenado por score desc. `pendentes=true` = sem rótulo.
- `GET /casos/{id}` → `{transacao, decisao, rotulo, historico_origem: últimas 20 tx da origem, grafo: subgrafo_2_saltos(destino)}`; 404 se não existir.
- `POST /casos/{id}/rotulo` body `{rotulo: "fraude"|"legitima", analista: str}` → upsert; se `fraude`, adiciona o destino ao conjunto Redis `contas_fraude`.
- `POST /casos/{id}/resumo` → `{resumo, fonte: "llm"|"template"}`. `llm.py`: se `ANTHROPIC_API_KEY` definido, chama `anthropic.Anthropic().messages.create(model=LLM_MODEL, max_tokens=400, ...)` pedindo, em PT-BR, 3 frases de resumo + 1 recomendação, com os dados do caso em JSON; em qualquer erro ou sem chave, usa template determinístico com os 3 principais motivos.
- `GET /metricas` → `{total, por_decisao:{APROVAR,REVISAR,BLOQUEAR}, valor_bloqueado, latencia_ms:{p50,p95,p99}, rotulados, precisao_rotulos (fração de rotulados como fraude entre REVISAR/BLOQUEAR rotulados), modelo: conteúdo de modelo_meta.json}`.

## FRONTEND (`frontend/src`)
- `lib/api.ts`: `API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000"`, funções tipadas para cada endpoint; `lib/tipos.ts` com os tipos.
- `app/providers.tsx` com QueryClientProvider; layout com barra lateral fixa (Painel, Fila de casos) e tema escuro (fundo slate-950, cards slate-900, borda slate-800, destaque emerald para APROVAR, amber REVISAR, rose BLOQUEAR).
- `app/page.tsx` — Painel: 4 cards (total analisado, % em revisão, valor bloqueado R$, latência p99 ms), card "Modelo" (versão, PR-AUC, precisão/recall@0.4), barra horizontal simples em CSS com distribuição por decisão, refetch a cada 5 s.
- `app/casos/page.tsx` — Fila: abas REVISAR/BLOQUEAR, toggle "só pendentes", tabela (hora, origem, destino, valor R$, score com barra colorida, decisão em badge, rótulo); linha clicável → detalhe; refetch 5 s.
- `app/casos/[id]/page.tsx` — Detalhe: cabeçalho com valor, decisão e score; lista de motivos (regras primeiro, depois SHAP com barra proporcional ao |impacto|, cor rose se aumenta risco e emerald se reduz); tabela do histórico da origem; grafo em SVG próprio (layout radial: destino no centro, 1º salto no anel interno, 2º no externo; nós laranja/fraude em rose); botão "Gerar resumo" (mostra texto e fonte); botões "Confirmar fraude" e "Marcar legítima" com campo analista (padrão "analista.demo"), invalidando queries após sucesso.
- Formatação BRL com `Intl.NumberFormat("pt-BR", {style:"currency", currency:"BRL"})`.
- Sem libs além de react-query.

## TESTES (`backend/tests`) — usar SQLite em memória e fakeredis
- `conftest.py`: override de settings (DATABASE_URL sqlite, REDIS fake), fixture que gera 300 contas × 5 dias, treina modelo pequeno (n_estimators=30) em diretório tmp.
- `test_gerador.py`: determinismo com mesma seed; taxa de fraude entre 0.5% e 5%; três padrões presentes.
- `test_features.py`: **consistência online/offline** — mesma sequência de 500 tx produz features idênticas em `EstadoMemoria` e `EstadoRedis` (fakeredis); janelas de 5m/1h corretas num caso construído à mão.
- `test_regras.py`: um caso por ramo das regras.
- `test_modelo.py`: score em [0,1]; `explicar` retorna 5 itens com chaves certas.
- `test_api.py` (TestClient): /health; /decisao retorna campos e é idempotente com mesmo id; /casos ordenado por score; rótulo gravado; /resumo sem chave retorna fonte "template"; /metricas.

## INFRA
- `docker-compose.yml`: `postgres` (16, user/senha/db sentinela, healthcheck), `redis` (7), `api` (build backend, `uvicorn sentinela.api.main:app --host 0.0.0.0 --port 8000`, depends_on healthy, volume `./backend/artifacts:/app/artifacts`), `consumer` (mesma imagem, `python -m sentinela.consumer`), `frontend` (node:22-alpine, working_dir /app, volume ./frontend, comando `sh -c "npm ci && npm run dev -- -H 0.0.0.0"`, porta 3000). Variáveis de ambiente apontando para os hosts `postgres` e `redis`.
- `backend/Dockerfile`: python:3.12-slim, `apt-get install -y libgomp1`, pip install -r requirements.txt, WORKDIR /app, COPY.
- `Makefile`: `up` (compose up -d --build), `down`, `seed` (`docker compose exec api python -m sentinela.seed`), `stream` (`docker compose exec api python -m sentinela.produtor --tps 10 --minutos 10`), `test` (`cd backend && pytest -q`), `lint` (`cd backend && ruff check .`), `logs`.
- `.github/workflows/ci.yml`: job `backend` (python 3.12, pip install, ruff check, pytest) e job `frontend` (node 22, npm ci, npm run lint, npm run build) em push e PR.
- `.gitignore`: node_modules, .next, __pycache__, .venv, .env, backend/artifacts/* exceto .gitkeep.

## FASES
1. Estrutura, config, db, docker-compose, Dockerfile, Makefile, .gitignore, .env.example. Commit.
2. gerador.py + test_gerador. Commit.
3. features.py, grafo.py + test_features. Commit.
4. treino.py, modelo.py, regras.py, decisao.py, seed.py + test_regras, test_modelo. Rodar seed localmente com SQLite se Docker indisponível, só para validar. Commit.
5. API completa + llm.py + test_api. Commit.
6. produtor.py e consumer.py. Commit.
7. Frontend (3 páginas). `npm run build` precisa passar. Commit.
8. CI + README (pitch em 2 linhas, diagrama Mermaid gerador→Redis Streams→consumer→Postgres←API←Next.js, como rodar: `make up && make seed && make stream` e abrir localhost:3000, métricas do modelo, seção "Decisões técnicas" com 1 parágrafo cada: Redis Streams vs Kafka, consistência online/offline das features, split temporal e vazamento, regras + modelo, idempotência, feedback loop do analista, limitações de dados sintéticos). Commit e push final.
