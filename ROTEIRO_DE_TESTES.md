# Roteiro de testes — Sentinela Pix

Roteiro manual completo, do mais rápido ao mais profundo. Cada caso tem passos e o resultado esperado; marque a caixa quando passar. Os comandos partem da raiz do repositório, salvo indicação.

Tempo total: cerca de 30 minutos (5 deles esperando o stream).

## 0. Preparação

- [ ] **P1 — Docker disponível.** `docker compose version` responde.
- [ ] **P2 — Portas livres.** 3000, 8000, 6379 e 5432 precisam estar livres:

  ```bash
  ss -ltn | grep -E ':(3000|8000|5432|6379)\b'
  ```

  Esperado: nenhuma linha. Se a 5432 estiver ocupada por outro Postgres, crie um override local (o Compose o carrega sozinho) que deixa de publicar essa porta, e **não o commite**:

  ```bash
  printf 'services:\n  postgres:\n    ports: !reset []\n' > docker-compose.override.yml
  ```

- [ ] **P3 — Ambiente Python.** `.venv/bin/python --version` responde (os testes do backend usam essa venv).

## 1. Testes automatizados (sem Docker)

- [ ] **A1 — Lint do backend.**

  ```bash
  cd backend && ../.venv/bin/ruff check .
  ```

  Esperado: `All checks passed!`

- [ ] **A2 — Testes do backend.**

  ```bash
  cd backend && ../.venv/bin/pytest -q
  ```

  Esperado: `27 passed`. Cobrem gerador, consistência online/offline das features, regras, modelo, API, produtor e consumer.

- [ ] **A3 — Lint e build do frontend.**

  ```bash
  cd frontend && npm run lint && npm run build
  ```

  Esperado: build conclui listando as rotas `/`, `/casos` e `/casos/[id]`.

- [ ] **A4 — CI.** Em `https://github.com/p3dru/sentinela_pix/actions`, a execução do último commit está verde nos jobs `backend` e `frontend`.

## 2. Subida e seed

- [ ] **S1 — Subida com banco vazio.**

  ```bash
  make up
  ```

  ```bash
  docker compose ps -a --format '{{.Service}} {{.Status}}'
  ```

  Esperado: `postgres`, `redis`, `api`, `consumer` e `frontend` todos `Up`. O consumer fica `Up` mesmo sem modelo, aguardando o seed.

- [ ] **S2 — API sem modelo.**

  ```bash
  curl -s localhost:8000/health
  ```

  Esperado: `{"status":"ok","modelo_versao":null}`. Um `POST /decisao` neste ponto devolve 503 com "rode make seed".

- [ ] **S3 — Seed.**

  ```bash
  make seed
  ```

  Esperado: cerca de 1 minuto; imprime as contas e transações inseridas e, ao final, as métricas do modelo (`pr_auc`, limiares 0.4 e 0.85, `taxa_fraude_teste` perto de 2%).

- [ ] **S4 — Modelo carregado sem reiniciar.**

  ```bash
  curl -s localhost:8000/health
  ```

  Esperado: `modelo_versao` preenchida (`v<data e hora>`), **sem** ter reiniciado nenhum container. A hora embutida na versão deve bater com o seu relógio (fuso de Brasília).

- [ ] **S5 — Consumer vivo após o seed.** `docker compose ps` mostra `consumer` `Up`, sem reinícios.

## 3. API (curl)

- [ ] **API1 — Métricas.**

  ```bash
  curl -s localhost:8000/metricas | python3 -m json.tool
  ```

  Esperado: `total` 3000; `por_decisao` com APROVAR, REVISAR e BLOQUEAR; `valor_bloqueado`; `latencia_ms` com p50, p95 e p99; `modelo.versao` igual à do `/health`.

- [ ] **API2 — Decisão bloqueada por regra.** Dispositivo novo, de madrugada, valor acima de 2000:

  ```bash
  curl -s -X POST localhost:8000/decisao -H 'content-type: application/json' -d '{"id":"roteiro-1","ts":"2026-11-13T03:00:00","origem":"conta-00001","destino":"conta-00002","valor":2500,"dispositivo":"dev-roteiro"}' | python3 -m json.tool
  ```

  Esperado: `decisao` `BLOQUEAR`; o primeiro item de `motivos` tem `feature: "regra"`; depois vêm 5 motivos SHAP; `transacao_id` `roteiro-1`.

- [ ] **API3 — Idempotência.** Repita o comando do API2 trocando `valor` para `9999`. Esperado: resposta **idêntica** à primeira (mesmo score, mesma `latencia_ms`); a transação não é reprocessada.

- [ ] **API4 — Validação.** Envie `"valor": -5`. Esperado: HTTP 422.

- [ ] **API5 — Fila ordenada.**

  ```bash
  curl -s "localhost:8000/casos?decisao=BLOQUEAR&pendentes=true&limit=5" | python3 -m json.tool
  ```

  Esperado: `itens` em ordem decrescente de `score`, todos com `rotulo: null`, e `total` maior ou igual ao número de itens.

- [ ] **API6 — Detalhe e 404.**

  ```bash
  curl -s localhost:8000/casos/roteiro-1 | python3 -m json.tool | head -40
  ```

  Esperado: chaves `transacao`, `decisao`, `rotulo` (null), `historico_origem` (até 20) e `grafo` com `nodes` e `edges`.

  ```bash
  curl -s -o /dev/null -w '%{http_code}\n' localhost:8000/casos/nao-existe
  ```

  Esperado: `404`.

- [ ] **API7 — Rótulo e feedback.**

  ```bash
  curl -s -X POST localhost:8000/casos/roteiro-1/rotulo -H 'content-type: application/json' -d '{"rotulo":"fraude","analista":"roteiro"}'
  ```

  ```bash
  docker compose exec redis redis-cli smembers contas_fraude
  ```

  Esperado: o rótulo é devolvido e `conta-00002` aparece no conjunto do Redis. Um rótulo inválido (`"rotulo":"talvez"`) devolve 422.

- [ ] **API8 — Resumo sem chave.**

  ```bash
  curl -s -X POST localhost:8000/casos/roteiro-1/resumo
  ```

  Esperado: `fonte: "template"` e um texto com valor, contas, score e os principais motivos.

## 4. Streaming

- [ ] **ST1 — Produtor e consumer.** Anote o `total` de `/metricas` e ligue o stream por 1 minuto:

  ```bash
  docker compose exec api python -m sentinela.produtor --tps 10 --minutos 1
  ```

  Esperado: ao final, `total` de `/metricas` cresceu cerca de 600.

- [ ] **ST2 — Logs do consumer.**

  ```bash
  docker compose logs consumer | grep "msgs |"
  ```

  Esperado: uma linha a cada 100 mensagens, com tps e latência média.

- [ ] **ST3 — Fila zerada.**

  ```bash
  docker compose exec redis redis-cli xpending pix:tx decisor
  ```

  Esperado: primeiro valor `0` (nenhuma mensagem pendente de confirmação).

- [ ] **ST4 — Versão única.**

  ```bash
  docker compose exec postgres psql -U sentinela -d sentinela -tc "select modelo_versao, count(*) from decisoes group by 1"
  ```

  Esperado: uma única versão, igual à do `/health`.

## 5. Console no navegador

Abra `http://localhost:3000`. Para os casos com atualização ao vivo, deixe `make stream` rodando em outro terminal.

### Painel

- [ ] **C1 — Cards.** Quatro cards preenchidos: total analisado, % em revisão, valor bloqueado em R$ e latência p99 em ms.
- [ ] **C2 — Atualização ao vivo.** Com o stream ligado, "Total analisado" muda sozinho a cada 5 segundos.
- [ ] **C3 — Distribuição e modelo.** A barra mostra as três decisões em verde, âmbar e rosa; o card "Modelo" mostra versão, PR-AUC, precisão e recall @0.4.
- [ ] **C4 — Navegação.** "Painel" aparece destacado na barra lateral; o título da aba é "Painel · Sentinela Pix".

### Fila de casos

- [ ] **C5 — Abas.** REVISAR e BLOQUEAR trocam a lista; o contador mostra "1–N de N".
- [ ] **C6 — Só pendentes.** Desmarcar o filtro passa a incluir casos já rotulados (como o `roteiro-1`).
- [ ] **C7 — Tabela.** Cada linha tem hora, origem, destino, valor em R$, barra de score colorida, badge da decisão e rótulo.
- [ ] **C8 — Paginação.** Numa aba com mais de 50 casos, "Próxima" mostra os restantes e "Anterior" volta; trocar de aba volta à primeira página. Se nenhuma aba passar de 50, gere mais casos repetindo o comando do API2 com `id` diferentes.
- [ ] **C9 — Abrir caso.** Clicar em qualquer ponto da linha abre o detalhe.

### Detalhe do caso

- [ ] **C10 — Cabeçalho.** Valor, origem → destino, data, dispositivo, badge da decisão e score com três casas.
- [ ] **C11 — Motivos.** Regras primeiro (caixa âmbar), depois os motivos SHAP com barra proporcional: rosa quando aumenta o risco, verde quando reduz. Valores com no máximo duas casas; features binárias como "Sim"/"Não".
- [ ] **C12 — Grafo.** Destino no centro, 1º salto no anel interno, 2º no externo; contas laranja ou de fraude conhecida em rosa. Passar o mouse sobre um nó mostra a conta.
- [ ] **C13 — Histórico.** Tabela com as últimas transações da origem; a do caso aparece em destaque.
- [ ] **C14 — Resumo.** "Gerar resumo" mostra o texto e "Fonte: template".
- [ ] **C15 — Rótulo.** "Confirmar fraude" grava e mostra "Rotulado como fraude por analista.demo em <data>". A hora bate com o seu relógio.
- [ ] **C16 — Efeito do rótulo.** Voltando à fila com "só pendentes" marcado, o caso sumiu; no Painel, "Casos rotulados" subiu em 1.
- [ ] **C17 — Analista vazio.** Apagar o campo "Analista" desabilita os dois botões de rótulo.

## 6. Responsividade e teclado

- [ ] **R1 — Celular.** Estreite a janela para menos de 768 px (ou use o modo de dispositivo do navegador em 375 px). A barra lateral vira uma faixa no topo; nenhuma das três páginas tem rolagem horizontal da página; a tabela da fila rola dentro do próprio card.
- [ ] **R2 — Teclado.** Na fila, a tecla Tab chega ao link de hora de cada linha e Enter abre o detalhe. Abas, checkbox e botões também são alcançáveis.

## 7. Resiliência

- [ ] **RE1 — API fora do ar, Painel aberto.**

  ```bash
  docker compose stop api
  ```

  Esperado: em cerca de 30 segundos o Painel mostra "Sem conexão com a API; exibindo os últimos dados." e **mantém** os cards.

- [ ] **RE2 — API fora do ar, detalhe.** Abrir um caso mostra "Não foi possível carregar o caso." (e não "Caso não encontrado").
- [ ] **RE3 — Caso inexistente.** Suba a API de novo e abra `http://localhost:3000/casos/nao-existe`:

  ```bash
  docker compose start api
  ```

  Esperado: "Caso não encontrado." O Painel volta a atualizar sozinho.

- [ ] **RE4 — Consumer reinicia sozinho.** Derrube o processo por dentro do container (um `docker compose kill` conta como parada manual e **não** dispara o reinício):

  ```bash
  docker compose exec consumer sh -c 'kill -INT 1'
  ```

  Esperado: em cerca de 10 segundos `docker compose ps` mostra o consumer `Up` de novo (política `restart: unless-stopped`).

- [ ] **RE5 — Segundo seed.** Com o stream parado, rode `make seed` de novo. Esperado: `/health` passa a mostrar a versão nova sem reiniciar nada; o consumer continua `Up`; um novo `make stream` de 1 minuto é consumido normalmente e o ST4 mostra só a versão nova.
- [ ] **RE6 — Segundo seed com stream ligado (opcional).** Esperado: o consumer sobrevive e segue consumindo. As decisões feitas enquanto o seed treinava ficam no banco com a versão antiga; isso é esperado.
- [ ] **RE7 — Subida repetida.**

  ```bash
  make down && make up
  ```

  Esperado: API e consumer `Up` (a criação simultânea das tabelas não derruba a API). O banco não tem volume persistente, então é preciso rodar `make seed` de novo.

## 8. Resumo por LLM (opcional)

- [ ] **L1 — Com chave.** Coloque `ANTHROPIC_API_KEY=<sua chave>` num arquivo `.env` na raiz, rode `make up` e gere um resumo no detalhe de um caso. Esperado: "Fonte: llm", com três frases e uma recomendação em português.
- [ ] **L2 — Chave inválida.** Com uma chave errada, o resumo continua funcionando e a fonte volta a ser `template`.

## 9. Encerramento

- [ ] **E1 — Derrubar a stack.**

  ```bash
  make down
  ```

- [ ] **E2 — Limpeza.** Se criou o `docker-compose.override.yml` no P2, ele não deve ser commitado. `git status` não deve mostrar outras alterações.

## Limitações conhecidas

- **PR-AUC 1.0** é artefato dos dados sintéticos (a feature de distância a fraude conhecida entrega o rótulo); não representa desempenho real.
- **Fuso:** o sistema usa hora local sem fuso, fixada em Brasília no container. Quem abrir o console em outro fuso vê a hora de Brasília.
- **Sem testes automatizados de frontend:** as seções 5 a 7 são a cobertura do console.
- **Consumer bloqueado no instante do FLUSHDB:** só é exercitado pelo RE5/RE6, não por teste automatizado.
