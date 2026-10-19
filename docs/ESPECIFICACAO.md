# Radar de Demandas — prompt e especificação do sistema

> **Como usar (instruções para o humano):**
> 1. Antes de usar com dados reais, confirme com o gestor/TI se é permitido registrar informações de trabalho em serviços externos (Render e Neon ficam nos EUA).
> 2. Crie uma pasta vazia (ex.: `radar-demandas`), abra no VS Code e salve este arquivo como `docs/ESPECIFICACAO.md`.
> 3. No Claude Code, de preferência no modo de planejamento, envie: **Leia docs/ESPECIFICACAO.md por completo e execute somente a Fase 0.**
> 4. Aprove fase por fase. Senhas e connection strings vão direto no arquivo `.env`, nunca no chat.

---

## 1. Seu papel

Você é um desenvolvedor sênior em Python/Django e também meu mentor. Vamos construir do zero um sistema web **simples**, seguro e fácil de manter. Quero aprender durante o processo: explique as decisões importantes e, quando um conceito for muito técnico, acrescente uma analogia curta do dia a dia.

## 2. Contexto e objetivo

Recebi um feedback no trabalho com quatro pontos de melhoria. O **Radar de Demandas** é minha ferramenta pessoal para responder a eles, começando pelo principal: registrar, priorizar e acompanhar tudo o que chega para mim.

| Ponto do feedback | Como a v1 responde |
|---|---|
| Anotar as demandas que chegam, sem deixar nada passar, e organizar prioridades | Captura rápida, caixa de entrada, prioridade e prazo, Painel do dia e Top 3 |
| Acompanhar com atenção e-mails e circulares | A origem da demanda registra "E-mail" e "Circular", e o resumo mostra quantas chegaram por esses canais (módulo próprio fica para depois) |
| Manter o foco durante o expediente | Uso no computador do trabalho, com o Top 3 do dia como norte |
| Colocar em prática o que aprendi nos cursos | O próprio projeto, construído com explicações didáticas |

**Princípio central:** registrar uma demanda tem que ser mais rápido do que esquecê-la. Captura em segundos; detalhes e triagem depois.

## 3. Regras de trabalho (valem para todas as fases)

1. **Fases com pausa.** Siga a ordem da seção 13. Ao fim de cada fase, pare e aguarde eu responder "Fase N aprovada".
2. **Fase 0 sem código.** Primeiro o plano; arquivos só depois da aprovação.
3. **Simplicidade.** Um único serviço web (Django) e um banco (PostgreSQL no Neon). Sem microsserviços, filas, Celery, Redis, Docker obrigatório, SPA ou framework JavaScript.
4. **Escopo fechado.** Nada além da seção 5. Ideias extras vão para "Ideias futuras" no README.
5. **Dependências.** Só bibliotecas consolidadas e mantidas. Para cada nova: motivo, comando de instalação, riscos de segurança conhecidos e alternativa considerada. Versões fixadas no `requirements.txt`.
6. **Segredos.** Nunca coloque senhas, `SECRET_KEY` ou connection strings no código, em logs, em commits ou no chat. Use `.env` (listado no `.gitignore`) e um `.env.example` só com os nomes das variáveis. Eu preencho os valores reais; nunca me peça para colá-los aqui.
7. **Banco de produção.** Você nunca executa comandos contra o banco de produção. Quando for preciso, me passe o comando e eu rodo.
8. **Git.** Não faça commit nem push por conta própria; sugira o comando.
9. **Código.** SOLID, funções pequenas com responsabilidade única. Regras de negócio na camada de serviço (`services.py`) e consultas em `selectors.py`; views finas. Interface em pt-BR; nomes do domínio em português sem acento (`Demanda`, `prazo`). Quando houver mais de um caminho viável, explique o critério da escolha.
10. **Verificação.** Antes de encerrar cada fase: `ruff check`, testes e, a partir da Fase 2, `python manage.py check --deploy`. Mostre o resultado.
11. **Dúvida vira pergunta.** Se algo estiver ambíguo ou conflitar com esta especificação, pergunte antes de decidir.
12. **Memória do projeto.** Na Fase 1, crie um `CLAUDE.md` curto com estas regras, a stack, os comandos (rodar, testar, migrar) e a fase atual. Se mudarmos o escopo, atualize este arquivo e o `CLAUDE.md`.
13. **Sistema operacional.** Detecte o meu e dê comandos compatíveis (provavelmente Windows/PowerShell). O `build.sh` roda no Render, em Linux.

## 4. Stack e infraestrutura

| Camada | Escolha |
|---|---|
| Linguagem | Python 3.13 (ou 3.12), com a versão fixada no Render via `PYTHON_VERSION` ou `.python-version` |
| Framework | Django 5.2 LTS (suporte estendido até abril de 2028) |
| Banco | PostgreSQL no Neon (plano Free), em dois projetos: `radar-dev` (desenvolvimento, só dados fictícios) e `radar-prod` (produção) |
| Servidor | gunicorn, com WhiteNoise para os arquivos estáticos |
| Front-end | Templates do Django + Bootstrap 5.3 servido localmente (sem CDN) + JavaScript mínimo em arquivo estático |
| Hospedagem | Render, Web Service no plano Free, com deploy automático a cada push na `main` de um repositório **privado** no GitHub |
| Testes | Test runner do Django em PostgreSQL (`radar-dev`, com `--keepdb`). Não use SQLite: constraints e fuso dependem do Postgres |
| Qualidade | `ruff` e `pip-audit` |

**Dependências previstas** (confirme as versões na Fase 0):

| Pacote | Para quê | Instalação | Riscos e cuidados |
|---|---|---|---|
| Django 5.2 LTS | Framework | `pip install "Django>=5.2,<5.3"` | Correções de segurança frequentes: manter o patch 5.2.x em dia. `DEBUG=True` em produção expõe configurações |
| psycopg 3 | Driver PostgreSQL | `pip install "psycopg[binary]>=3.2"` | O pacote binário embute libpq/OpenSSL: atualizar para receber correções |
| dj-database-url | Ler a `DATABASE_URL` | `pip install dj-database-url` | Baixo. Nunca imprimir nem logar a URL (ela contém a senha) |
| gunicorn | Servidor WSGI | `pip install "gunicorn>=23"` | Versões antigas tiveram falhas de *request smuggling* (ex.: CVE-2024-1135). Usar versão atual |
| whitenoise | Servir estáticos | `pip install whitenoise` | Baixo. Serve só o que foi coletado no build |
| django-axes | Bloqueio de força bruta no login | `pip install django-axes` | Guarda IP e usuário das tentativas (dado pessoal): retenção curta. Atrás do proxy do Render, configurar o IP real |
| python-dotenv | Carregar o `.env` local | `pip install python-dotenv` | Baixo. O risco real é commitar o `.env` |
| ruff e pip-audit (dev) | Lint e auditoria de vulnerabilidades | `pip install ruff pip-audit` | Só desenvolvimento |
| Bootstrap 5.3 (estático) | Layout | Baixar os arquivos minificados uma vez para `static/vendor/` | Versões antigas tiveram XSS; usar 5.3.x. Servir localmente evita CDN de terceiros e simplifica a CSP |

**Regiões:** Render em **Virginia** e `radar-prod` no Neon em **AWS US East (N. Virginia), `aws-us-east-1`**, um perto do outro. O `radar-dev` pode ficar em **AWS South America (São Paulo), `aws-sa-east-1`**, perto de mim, porque é usado pelo app rodando no meu computador. Nenhum dos dois serviços permite trocar a região depois da criação. O Render não tem região no Brasil; app e banco de produção em continentes diferentes adicionariam latência a cada consulta.

**Limites do plano gratuito que o projeto precisa respeitar** (conferidos em 19/10/2026; podem mudar):

- **Render Free:** hiberna após 15 min sem acesso e leva cerca de 1 min para voltar; 750 h/mês por workspace (se acabarem, os serviços Free ficam suspensos até o mês seguinte); 0,1 CPU e 512 MB de RAM; disco efêmero, sem disco persistente; sem Shell/SSH e sem *one-off jobs*; *pre-deploy command* só em planos pagos; portas de saída 25/465/587 (SMTP) bloqueadas; banda e minutos de build contam na cota mensal do workspace; o serviço pode ser reiniciado a qualquer momento; o próprio Render não recomenda o Free para produção.
- **Neon Free:** 100 CU-hora por projeto por mês (se esgotar, o banco fica suspenso até o ciclo seguinte); 1 GB por projeto (acima disso, gravações falham); pausa após 5 min sem consultas, sem opção de desativar, e acorda em algumas centenas de milissegundos; restauração (PITR) de apenas 6 h; 10 branches por projeto.

**Configuração do Django para esse ambiente:**

- `DATABASES` via `dj-database-url` lendo a `DATABASE_URL`, com SSL obrigatório.
- `CONN_MAX_AGE = 60` e `CONN_HEALTH_CHECKS = True`: o Neon fecha as conexões ao pausar, e o health check reconecta.
- `connect_timeout` de 10 s, recomendado pelo Neon por causa do *cold start*.
- Connection string **direta** (sem `-pooler`). Se um dia usar a pooled (PgBouncer em modo transação), ative `DISABLE_SERVER_SIDE_CURSORS = True`.
- `TIME_ZONE = "America/Sao_Paulo"`, `USE_TZ = True`, `LANGUAGE_CODE = "pt-br"`.
- `ALLOWED_HOSTS` e `CSRF_TRUSTED_ORIGINS` montados a partir de `RENDER_EXTERNAL_HOSTNAME`.
- gunicorn com 1 ou 2 workers (`WEB_CONCURRENCY`), por causa dos 512 MB.

**Deploy no Render:**

- Build Command: `bash build.sh`, que roda `pip install -r requirements.txt`, `python manage.py collectstatic --no-input` e `python manage.py migrate --no-input`. As migrações ficam no build porque o *pre-deploy command* é pago. Se o build falhar, o Render cancela o deploy e a versão anterior continua no ar.
- Start Command: `gunicorn config.wsgi:application`.
- `render.yaml` (Blueprint) com `plan: free`, região Virginia, `DATABASE_URL` com `sync: false` (eu preencho no painel) e `SECRET_KEY` gerada pelo próprio Render.
- Rota `/saude` que responde 200 **sem consultar o banco**, tratada no topo da pilha de middlewares (antes do redirecionamento HTTPS e da validação de Host) para não falhar se for usada como health check.

## 5. Escopo funcional da v1

### 5.1 Acesso (usuário único)

- Um único usuário, criado por comando (`createsuperuser`). **Sem tela de cadastro.**
- Usuário customizado (`AbstractUser`) desde o início, como recomenda a documentação do Django.
- Todas as páginas exigem login (`LoginRequiredMiddleware`), exceto o próprio login e `/saude`.
- Logout, troca de senha com o usuário logado e sessão que expira em 12 h.
- Admin do Django em caminho definido por variável de ambiente (`ADMIN_URL`), usado só para cadastros auxiliares (categorias).
- `robots.txt` e `noindex` para o site não aparecer em buscadores.

### 5.2 Demandas (núcleo)

- **Captura rápida em todas as telas:** campo "Nova demanda…" no topo, com seletor opcional de origem ao lado (padrão: Outro). Título + Enter cria a demanda com status **Nova** (caixa de entrada). O atalho `n` leva ao campo.
- **Triagem:** revisar prioridade, prazo, origem e categoria e tirar a demanda de Nova. Uma demanda nunca volta para Nova.
- **Campos:** título*, descrição, solicitante (nome ou área), origem*, categoria, referência (cliente, sistema ou processo, por nome ou código interno; nunca CPF), prioridade*, prazo, recebida em* (padrão: agora, editável para registrar algo que chegou antes) e status*. Ao marcar "Aguardando terceiro", informar de quem ou do quê.
- **Origens:** E-mail, Circular, Chat (Teams/WhatsApp), Telefone, Presencial, Reunião, Sistema, Outro.
- **Prioridades:** Alta, Média (padrão), Baixa.
- **Status:** Nova, A fazer, Em andamento, Aguardando terceiro, Concluída, Cancelada (transições na seção 7).
- **Histórico** por demanda: criação, mudanças de status, prioridade e prazo, e anotações livres. Só inclusão; o histórico não se edita.
- **Lista** com filtros (status, prioridade, origem, categoria, período, atrasadas), busca por texto (título, descrição, solicitante) e paginação.
- **Ações rápidas:** iniciar, aguardar, concluir, reabrir, editar e excluir (com confirmação).
- **Aviso de dado pessoal:** ao salvar, se algum texto parecer conter CPF (dígitos verificadores válidos, ignorando sequências repetidas como 111.111.111-11), mostrar um aviso, sem bloquear.

### 5.3 Painel do dia (página inicial)

Blocos, nesta ordem:

1. **Top 3 do dia:** até 3 demandas escolhidas por mim para hoje, com o botão "Trazer pendentes do último Top 3".
2. **Caixa de entrada:** demandas Nova a triar (meta: zerar até o fim do dia).
3. **Atrasadas:** prazo antes de hoje e status aberto.
4. **Vencem hoje.**
5. **Próximos 7 dias.**
6. **Aguardando terceiro:** com "há N dias" e destaque a partir de 3 dias (hora de cobrar).
7. **Abertas sem prazo:** contador com link.
8. **Concluídas hoje.**
9. Rodapé com o total de abertas e link para a lista completa.

Ordenação padrão: atrasadas primeiro (prazo mais antigo), depois prioridade (Alta → Baixa), prazo mais próximo (sem prazo por último) e recebida há mais tempo.

### 5.4 Resumo do período (acompanhar minha evolução)

- Período: mês atual por padrão, com seletor de mês e intervalo personalizado.
- Indicadores:
  - recebidas e concluídas no período;
  - % concluídas no prazo: entre as concluídas que tinham prazo, quantas terminaram até a data do prazo (informar quantas não tinham prazo);
  - tempo de conclusão, de `recebida_em` até `concluida_em`, em dias corridos (média e mediana);
  - atrasadas hoje;
  - distribuição por origem, categoria e prioridade;
  - recebidas × concluídas por semana (segunda a domingo), em tabela com barras simples em CSS, sem biblioteca de gráficos.
- Versão para impressão (`@media print`) e exportação CSV do período, para levar às conversas de feedback.

### 5.5 Privacidade e dados

- **Exportar tudo:** CSV para Excel (separador `;`, UTF-8 com BOM) e backup completo em JSON compatível com `python manage.py loaddata`. O backup contém dados de trabalho e o hash da senha: a tela deve avisar para guardá-lo em local seguro.
- **Excluir:** uma demanda (com confirmação) ou "Apagar todos os meus dados" (confirmação digitando EXCLUIR).
- **Retenção:** tela que lista concluídas e canceladas há mais de `RETENCAO_MESES` (padrão 12) para exportar e excluir **manualmente**. Nada é apagado automaticamente.
- **Página "Privacidade":** o que é guardado, para quê, onde fica (Render e Neon, nos EUA) e como exportar ou apagar.

## 6. Modelo de dados (ponto de partida; revise na Fase 0)

```text
Usuario (AbstractUser) — sem campos extras na v1

Categoria
  usuario → Usuario (CASCADE) · nome (≤ 60, não vazio) · ativa (bool, padrão true)
  UNIQUE (usuario, lower(nome))

Demanda
  usuario → Usuario (CASCADE)
  titulo (≤ 200, não vazio) · descricao (texto, opcional)
  solicitante · referencia · aguardando_quem (≤ 120 cada, opcionais)
  origem     ∈ {email, circular, chat, telefone, presencial, reuniao, sistema, outro}
  categoria → Categoria (SET NULL, opcional)
  prioridade ∈ {alta, media, baixa}                                         padrão media
  status     ∈ {nova, a_fazer, em_andamento, aguardando, concluida, cancelada}  padrão nova
  prazo (date, opcional)
  recebida_em · status_alterado_em · criada_em · atualizada_em (timestamptz)
  concluida_em (timestamptz, opcional)
  versao (inteiro, padrão 1) — trava do lock otimista (decisão da Fase 0)
  CHECK origem, prioridade e status dentro dos valores válidos
  CHECK (status = 'concluida') ⇔ (concluida_em IS NOT NULL)
  CHECK (status = 'aguardando') ⇔ (aguardando_quem não vazio) — limpo ao sair do status
  CHECK titulo não vazio nem só com espaços
  ÍNDICES (usuario, status, prazo) · (usuario, recebida_em) · (usuario, concluida_em)

EventoDemanda  (histórico; só inclusão)
  demanda → Demanda (CASCADE)
  tipo ∈ {criada, status, prioridade, prazo, nota, edicao}
  valor_anterior · valor_novo (≤ 60, opcionais) · texto (opcional) · criado_em
  ÍNDICE (demanda, criado_em)

FocoDoDia  (Top 3)
  usuario → Usuario (CASCADE) · data (date) · ordem (1 a 3) · demanda → Demanda (CASCADE)
  UNIQUE (usuario, data, ordem) · UNIQUE (usuario, data, demanda) · CHECK ordem BETWEEN 1 AND 3
```

Atenção: `choices` do Django não cria restrição no banco. Crie as `CheckConstraint` explicitamente.

## 7. Regras de negócio e integridade (ACID)

- **Atomicidade:** toda operação que grava em mais de uma tabela roda em `transaction.atomic()` na camada de serviço: criar demanda + evento "criada"; mudar status + evento; montar o Top 3 do dia; apagar todos os dados; exclusão por retenção.
- **Consistência:** regras críticas no banco (FK, NOT NULL, CHECK, UNIQUE), não só no formulário. Concluir preenche `concluida_em`; reabrir limpa. Toda mudança de status atualiza `status_alterado_em`.
- **Isolamento:** o READ COMMITTED padrão do PostgreSQL basta. O limite do Top 3 é garantido pelas constraints, não por "contar antes de inserir".
- **Durabilidade:** o commit no PostgreSQL é durável, mas o PITR do Neon Free cobre só 6 h. O backup JSON é a cópia de segurança, e a restauração precisa ser testada (Fase 6).
- **Edição concorrente:** o formulário envia `versao` (decisão da Fase 0; `atualizada_em` fica só para exibição); se o registro mudou depois que a tela foi aberta (outra aba), não sobrescreva: avise e recarregue (lock otimista).
- **Tempo:** uma única fonte de "agora" e "hoje" (ex.: `core/relogio.py`) no fuso America/Sao_Paulo. Nunca fixe `-03:00` no código. Isso também permite testar "vence hoje" às 23h30 sem bibliotecas extras.
- **Migrações:** versionadas e revisadas. Mudanças incompatíveis em duas etapas (adicionar → migrar dados → remover), porque o build migra o banco enquanto a versão antiga ainda atende.
- **Transições de status** (definidas em um único lugar e testadas):
  - Abertas: Nova, A fazer, Em andamento, Aguardando terceiro. Fechadas: Concluída, Cancelada.
  - Entre abertas, qualquer mudança é permitida, exceto voltar para Nova.
  - De aberta para fechada: permitido.
  - De fechada: apenas reabrir para A fazer.

## 8. Segurança

- `DEBUG=False` em produção; `SECRET_KEY` obrigatória via ambiente (o app não sobe sem ela).
- HTTPS: `SECURE_PROXY_SSL_HEADER`, `SECURE_SSL_REDIRECT`, cookies `Secure`, `HttpOnly` e `SameSite=Lax`, HSTS começando com valor baixo.
- CSRF do Django em todos os formulários; ações que alteram dados só via POST.
- Força bruta: django-axes lendo o IP real atrás do proxy do Render, sem confiar cegamente no `X-Forwarded-For` (que pode ser forjado), e com limpeza periódica dos registros antigos.
- Toda consulta filtra por `usuario=request.user` (evita acessar registros trocando o ID na URL, o chamado IDOR).
- Autoescape dos templates sempre ativo; nunca usar o filtro `safe` em texto digitado pelo usuário.
- Content Security Policy simples via middleware próprio (o Django 5.2 não tem CSP nativo), sem scripts inline.
- `pip-audit` sem vulnerabilidades conhecidas antes de cada deploy.
- Logs sem dados pessoais e sem conteúdo das demandas.
- Páginas 404 e 500 próprias, sem stack trace.

## 9. LGPD (Lei nº 13.709/2018, em vigor desde 18/09/2020)

Orientação prática de projeto, não parecer jurídico. A empresa é a controladora dos dados de trabalho; o uso deve ser validado com o encarregado (DPO) dela.

- **Finalidade e necessidade (art. 6º, I e III):** guardar só o necessário para organizar demandas de trabalho. Não registrar CPF, RG, dados bancários, salários nem dados sensíveis (art. 5º, II, ex.: saúde) de clientes ou colegas. Cliente identificado por nome da empresa ou código interno.
- **Transparência (art. 6º, VI):** página "Privacidade".
- **Segurança (art. 46):** seção 8.
- **Direitos do titular (art. 18):** exportação e exclusão (seção 5.5).
- **Transferência internacional (art. 33):** Render e Neon (produção) processam e armazenam nos EUA. É mais um motivo para minimizar dados e usar dados reais só depois da validação com gestor/TI.
- **Incidente (art. 48):** o README deve trazer o passo a passo: trocar a senha do banco no Neon, gerar nova `SECRET_KEY`, revisar acessos e comunicar o encarregado da empresa.
- **Desenvolvimento:** só dados fictícios no `radar-dev`.

## 10. Interface

- Desktop first (computador do trabalho), sem quebrar em telas menores.
- Identidade visual: **tema escuro** profissional (alterado a pedido em 19/10/2026), com fundo `#0A0F13`, superfícies `#11181D`, texto `#E6EDF1`, marca azul-petróleo `#0F4C5C` no logotipo, botões em `#0F766E` e destaques em `#2DD4BF`. Menu lateral com ícones e barra de captura fixa no topo.
- Prioridade e status sempre com cor **e** texto, sem depender só da cor (etiquetas com texto claro sobre fundo tingido: Alta vermelho, Média âmbar, Baixa cinza, Concluída verde). Contraste mínimo WCAG AA. A impressão sai em fundo branco.
- Padrão brasileiro: datas `dd/mm/aaaa`, "há 3 dias", textos em pt-BR.
- Menos cliques: captura rápida em todas as telas, atalhos `n` (nova) e `/` (busca), foco automático nos campos.
- Estados vazios amigáveis (ex.: "Caixa de entrada zerada. Bom trabalho!").

## 11. Cenários de falha e mitigação

| # | Cenário | Mitigação |
|---|---|---|
| 1 | Primeiro acesso após 15 min parado demora cerca de 1 min (o Render hiberna) | Comportamento aceito na v1 e explicado no README. Não usar "pingers" para manter o serviço acordado |
| 2 | Neon pausa após 5 min sem consultas e fecha as conexões | `CONN_HEALTH_CHECKS`, `connect_timeout=10` e mensagem amigável ("tente novamente") em caso de `OperationalError` |
| 3 | Algo mantém o banco acordado 24/7 e esgota as 100 CU-hora do mês | `/saude` sem consulta ao banco, sem polling nem tarefas periódicas e nenhuma transação deixada aberta |
| 4 | Armazenamento de 1 GB cheio e gravações falhando | Só texto, limite de tamanho nos campos, sem anexos; acompanhar o uso no console do Neon |
| 5 | Disco efêmero apaga arquivos a cada deploy ou reinício | Nada gravado em disco; estáticos gerados no build e servidos pelo WhiteNoise |
| 6 | Render reinicia o serviço a qualquer momento | Nenhum estado em memória; sessões no banco |
| 7 | Migração falha no build | O deploy é cancelado e a versão anterior continua no ar. Testar antes no `radar-dev` |
| 8 | Push com erro publica direto em produção (deploy automático) | Rodar testes e `check --deploy` antes de cada push; se quebrar, reverter o commit |
| 9 | `build.sh` criado no Windows quebra no Render (fim de linha CRLF ou sem permissão de execução) | `.gitattributes` com `*.sh text eol=lf` e Build Command `bash build.sh` |
| 10 | "Vence hoje" errado à noite (servidor em UTC) | `USE_TZ`, `America/Sao_Paulo`, fonte única de "hoje" e testes às 23h30 e 00h30 |
| 11 | Duplo clique cria demanda duplicada | Padrão POST → redirect → GET e botão desabilitado após o envio |
| 12 | Mesma demanda editada em duas abas | Lock otimista com `versao` |
| 13 | Esqueci a senha (sem e-mail, porque o SMTP é bloqueado no Free) | `python manage.py changepassword` rodado localmente contra o banco de produção, com passo a passo no README |
| 14 | Comando rodado no banco errado | `.env` local aponta só para o `radar-dev`; produção apenas com `DATABASE_URL` definida no próprio terminal, conforme o README |
| 15 | Força bruta no login, ou bloqueio indevido porque o app enxerga só o IP do proxy | django-axes com leitura correta do IP real, senha forte e sem cadastro público |
| 16 | Segredo vazado (commit ou chat) | `.gitignore`, `.env.example` e repositório privado. Se vazar: trocar a senha no Neon e a `SECRET_KEY` |
| 17 | Perda de dados (exclusão acidental; PITR de só 6 h) | Confirmação nas exclusões, histórico, backup JSON periódico e restauração testada |
| 18 | Dado pessoal de cliente digitado por engano | Aviso de CPF, orientação nos formulários e tela de retenção |
| 19 | Região criada errada (não dá para trocar) | Conferir Virginia e `aws-us-east-1` antes de criar a produção |
| 20 | Regras do plano gratuito mudam | Backup em dia e README explicando como migrar (é PostgreSQL padrão) |
| 21 | Login lento (o hash de senha é pesado de propósito e a CPU é 0,1) | Esperado. Não reduzir a segurança do hash; sessão de 12 h |

## 12. Testes e critérios de aceite

Testes automatizados (em PostgreSQL) para:

- transições de status permitidas e proibidas;
- constraint concluída ⇔ `concluida_em`;
- atomicidade: forçar erro no meio de uma operação e confirmar que nada foi gravado;
- Top 3: o 4º item é rejeitado pelo banco;
- "atrasada" e "vence hoje" em horários-limite (23h30 e 00h30);
- cálculos do resumo (% no prazo, média e mediana);
- acesso sem login redirecionado para a tela de login;
- aviso de CPF (válido com pontuação, válido sem pontuação, dígito inválido, sequência repetida, número de telefone);
- exportação CSV e backup JSON.

Critérios de aceite da v1:

- Capturo uma demanda com título + Enter, de qualquer tela, em menos de 5 segundos.
- Nenhuma demanda some: o que não foi triado fica na caixa de entrada, e todo o resto aparece no painel ou na lista de abertas.
- `check --deploy` sem alertas, ou com cada alerta justificado.
- O backup JSON restaura todos os dados em um banco vazio.

## 13. Fases de entrega

| Fase | Entrega |
|---|---|
| 0. Plano (sem código) | Meu pedido resumido em 5 linhas; estrutura de pastas; diagrama ER em Mermaid; dependências com motivo, comando e riscos; decisões e alternativas; dúvidas para mim |
| 1. Fundação (local) | Projeto `config/` com apps `core`, `contas`, `demandas` e `painel`; settings por variável de ambiente; conexão com o `radar-dev`; usuário customizado; modelos e migrações com constraints; `/saude`; `CLAUDE.md`; README inicial; ruff |
| 2. Acesso, visual e 1º deploy | Login, logout e troca de senha; `LoginRequiredMiddleware`; django-axes; layout base com a identidade visual; páginas 404/500; cabeçalhos de segurança e CSP; `build.sh`, `.gitattributes`, `render.yaml` e passo a passo para eu criar o `radar-prod` e o serviço no Render. O deploy só acontece agora porque já existe login: antes disso, a URL pública ficaria aberta |
| 3. Demandas | Captura rápida, atalhos de teclado, triagem, cadastro e edição, transições, histórico atômico, filtros, busca, paginação, aviso de CPF, lock otimista e testes |
| 4. Painel do dia | Blocos e ordenação, Top 3 com constraints, "trazer pendentes" e testes de horários-limite |
| 5. Resumo do período | Indicadores, tabela semanal, versão para impressão, CSV do período e testes dos cálculos |
| 6. Privacidade, backup e entrega | Exportações, "apagar tudo", retenção, página Privacidade, restauração testada, `pip-audit`, `check --deploy` e README final (rodar local, deploy, administrar produção, resposta a incidente, ideias futuras) |

## 14. Fora do escopo da v1 (registrar em "Ideias futuras")

- Módulo de e-mails e circulares: resumo, "muda procedimento?", ciência e checklist diário.
- Aprendizados dos cursos ligados às demandas.
- Modo foco (Pomodoro).
- Acesso de leitura para o gestor.
- Integração com Outlook, Gmail, Teams ou WhatsApp; notificações; anexos; app mobile; recursos de IA.

## 15. Formato da sua resposta ao fim de cada fase

1. **O que mudou e por quê:** arquivos e decisões, em lista curta.
2. **Como testar:** comandos e o que devo ver.
3. **Conceito da fase:** uma ideia técnica explicada com analogia curta.
4. **Riscos e pendências.**
5. **Commit sugerido** no padrão semântico, ex.: `git commit -m "feat(demandas): adiciona captura rápida e histórico"`.

Depois disso, pare e aguarde "Fase N aprovada".

## 16. Mensagens curtas que vou usar para conduzir

- **Continuar:** "Fase N aprovada. Releia a Fase N+1 em docs/ESPECIFICACAO.md, resuma em 3 linhas o que vai fazer e comece."
- **Erro:** "Ao rodar `<comando>` apareceu este erro: `<erro, sem senhas>`. Explique a causa provável e corrija com a menor mudança possível."
- **Nova sessão:** "Leia o CLAUDE.md e o docs/ESPECIFICACAO.md, rode os testes e me diga em que fase estamos."
- **Revisão:** "Revise o projeto contra as seções 7, 8 e 9 e liste o que falta, sem alterar código."
