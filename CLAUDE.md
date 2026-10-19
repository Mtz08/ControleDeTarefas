# Radar de Demandas

Ferramenta pessoal para registrar, priorizar e acompanhar demandas de trabalho.
Especificação completa: `docs/ESPECIFICACAO.md` (fonte da verdade do escopo).

## Fase atual

**Fases 0 a 6 implementadas (v1 completa no código).** Pendente do usuário: preencher `.env`
com o `radar-dev`, rodar os testes no Neon e fazer o primeiro deploy (README, seção 2).

## Regras de trabalho

- Fases com pausa: ao fim de cada fase, parar e aguardar "Fase N aprovada".
- Escopo fechado (seção 5 da especificação); ideias extras vão para "Ideias futuras" no README.
- Simplicidade: um serviço Django e um PostgreSQL (Neon). Sem filas, Redis, Docker, SPA ou framework JS.
- Dependências novas: motivo, comando, riscos, alternativa; versão fixada nos requirements.
- Segredos só no `.env` (fora do git). Nunca pedir, exibir ou logar senha, `SECRET_KEY` ou `DATABASE_URL`.
- Nunca executar comandos contra o banco de produção; passar o comando para o usuário rodar.
- Nunca fazer commit nem push; sugerir o comando.
- Regras de negócio em `services.py`, consultas em `selectors.py`, views finas.
- Interface em pt-BR; nomes do domínio em português sem acento (`Demanda`, `prazo`).
- "Agora" e "hoje" só via `core/relogio.py` (testes usam `relogio.congelar`).
- Regras críticas também no banco (`CheckConstraint`/`UniqueConstraint`); `choices` não basta.
- Toda consulta filtra por `usuario=request.user`.
- Antes de encerrar uma fase: `ruff check`, `ruff format --check`, testes e (a partir da Fase 2) `check --deploy`.
- Resposta ao fim de cada fase no formato da seção 15 da especificação.

## Stack

Python 3.13 · Django 5.2 LTS · PostgreSQL (Neon: `radar-dev` local, `radar-prod` produção)
· gunicorn + WhiteNoise · Bootstrap 5.3 local · Render Free · ruff e pip-audit.

Apps: `core` (relógio, middlewares), `contas` (usuário, privacidade, exportação),
`demandas` (núcleo), `painel` (painel do dia, Top 3, resumo).

## Comandos (PowerShell, na raiz do projeto)

```powershell
.\.venv\Scripts\Activate.ps1                    # ativar o ambiente virtual
pip install -r requirements-dev.txt             # instalar dependências
python manage.py migrate                        # aplicar migrações no radar-dev
python manage.py runserver                      # rodar local
python manage.py test --keepdb                  # testes (PostgreSQL do radar-dev)
ruff check . ; ruff format --check .            # qualidade
python manage.py makemigrations                 # gerar migrações após mudar modelos
```

## Decisões registradas (Fase 0)

- Lock otimista com campo `versao` (inteiro), não com `atualizada_em`.
- `aguardando_quem` obrigatório só no status Aguardando; limpo ao sair (CHECK no banco).
- Busca com `icontains` (não ignora acentos).
- "Apagar todos os meus dados" mantém o usuário.
- Nome de categoria único por usuário sem diferenciar maiúsculas.

## Decisões de implementação (Fases 2–6)

- Limite do Top 3 garantido pelo banco: o serviço tenta cada posição em savepoint.
- IP real para o axes: `core/rede.py`, N-ésimo IP da direita do X-Forwarded-For (`PROXIES_CONFIAVEIS`).
- Erro de banco (Neon acordando) vira página 503 amigável em `core.views.erro_500`.
- Logs: `core.logs.SemDadosDoBancoFilter` remove detalhes de erros de banco.
- CSP sem inline; barras do resumo recebem largura via `static/js/radar.js` (`data-largura`).
- Sessões expiradas e tentativas do axes são limpas sem tarefa agendada (no login / cooloff).
- `security.W021` (HSTS preload) silenciado de propósito.
