# Radar de Demandas

Ferramenta pessoal para registrar, priorizar e acompanhar as demandas de trabalho:
captura em segundos, triagem depois, painel do dia com Top 3 e resumo do período.

Especificação completa em [docs/ESPECIFICACAO.md](docs/ESPECIFICACAO.md).

**Stack:** Python 3.13 · Django 5.2 LTS · PostgreSQL (Neon) · gunicorn + WhiteNoise ·
Bootstrap 5.3.8 servido localmente · Render (plano Free).

## Sumário

1. [Rodar no seu computador](#1-rodar-no-seu-computador)
2. [Primeiro deploy (Neon + Render)](#2-primeiro-deploy-neon--render)
3. [Rotina de cada deploy](#3-rotina-de-cada-deploy)
4. [Administrar a produção](#4-administrar-a-produção)
5. [Backup e restauração](#5-backup-e-restauração)
6. [Resposta a incidente](#6-resposta-a-incidente)
7. [Limites do plano gratuito](#7-limites-do-plano-gratuito)
8. [Estrutura do código](#8-estrutura-do-código)
9. [Ideias futuras](#9-ideias-futuras)

---

## 1. Rodar no seu computador

Pré-requisitos: Python 3.13 e um projeto **`radar-dev`** no [Neon](https://neon.tech),
região **AWS South America (São Paulo), `aws-sa-east-1`**, **só com dados fictícios**.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env
python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"
```

Abra o `.env` e preencha:

- `SECRET_KEY`: a chave gerada pelo último comando.
- `DATABASE_URL`: no console do Neon, projeto `radar-dev` → **Connect** → desligue
  **Connection pooling** (a URL **não** pode ter `-pooler`) e copie a connection string.

```powershell
python manage.py migrate
python manage.py createsuperuser        # seu usuário (sem tela de cadastro, de propósito)
python manage.py test --keepdb          # testes no PostgreSQL
python manage.py runserver
```

Acesse <http://127.0.0.1:8000>. Atalhos: **n** (nova demanda) e **/** (buscar).
Categorias são cadastradas no admin (`/admin/` localmente).

**Por que os testes usam o Neon e não SQLite?** As constraints e o fuso horário dependem
do PostgreSQL. O Django cria um banco `test_<nome>` dentro do `radar-dev`; `--keepdb`
o reaproveita. Cada execução consome um pouco das 100 CU-hora mensais.

**Qualidade, antes de cada push:**

```powershell
ruff check . ; ruff format --check .
python manage.py test --keepdb
pip-audit -r requirements.txt
```

## 2. Primeiro deploy (Neon + Render)

> A região **não pode ser trocada depois**. Confira antes de clicar em criar.

### 2.1 Banco de produção (`radar-prod`)

1. Neon → **New project** → nome `radar-prod`, região **AWS US East (N. Virginia), `aws-us-east-1`**.
2. **Connect** → desligue **Connection pooling** → copie a connection string. Não cole em chat,
   e-mail nem commit: ela vai direto para o painel do Render.

### 2.2 Repositório

```powershell
git init -b main            # se ainda não fez
git add .
git status                  # confira: .env e .venv NÃO podem aparecer
git commit -m "feat: radar de demandas v1"
```

No GitHub, crie um repositório **privado** (sem README) e:

```powershell
git remote add origin https://github.com/<seu-usuario>/radar-demandas.git
git push -u origin main
```

### 2.3 Serviço no Render

1. Render → **New** → **Blueprint** → escolha o repositório. O `render.yaml` cria o serviço
   `radar-demandas` no plano **Free**, região **Virginia**, com `SECRET_KEY` gerada pelo próprio Render.
2. Ele vai pedir as variáveis marcadas com `sync: false`:
   - `DATABASE_URL`: a connection string **direta** do `radar-prod`.
   - `ADMIN_URL`: um caminho difícil de adivinhar, terminado em `/` (ex.: `gestao-k3v9q2/`).
     Anote em local seguro.
3. Aguarde o build (`bash build.sh`: instala, coleta estáticos e migra). Ao final, `https://<serviço>.onrender.com/saude` deve mostrar `ok`.

### 2.4 Seu usuário em produção

O plano Free não tem Shell. Crie o usuário **do seu computador**, apontando para o `radar-prod`
só nesta janela do terminal (a variável do terminal vale mais que o `.env`):

```powershell
$env:DATABASE_URL = Read-Host "DATABASE_URL do radar-prod"   # colar aqui não fica no histórico
python manage.py createsuperuser
Remove-Item Env:DATABASE_URL                                  # volta a apontar para o radar-dev
```

Use senha forte (mínimo 12 caracteres). Feche e reabra o terminal se tiver dúvida de para onde ele aponta.

### 2.5 Conferir o IP real (proteção contra força bruta)

O django-axes bloqueia 5 erros seguidos do mesmo usuário no mesmo IP por 30 minutos.
Para isso, o app precisa enxergar o seu IP, e não o do proxy do Render:

1. Erre a senha **uma vez** em produção.
2. Entre no admin (`/<ADMIN_URL>`) → **Axes** → **Access attempts**: o IP registrado deve ser
   o seu IP público (compare com um site como "qual é meu IP").
3. Se aparecer um IP do Render/Cloudflare, mude `PROXIES_CONFIAVEIS` para `2` no painel do Render e repita.

### 2.6 HSTS

O HSTS começa com 1 hora (`HSTS_SEGUNDOS=3600`). Depois de alguns dias funcionando em HTTPS,
suba para `31536000` (1 ano) no painel do Render.

## 3. Rotina de cada deploy

Cada push na `main` publica em produção automaticamente. Antes do push:

1. Testes, ruff e `pip-audit` (seção 1).
2. Com migração nova: rode `python manage.py migrate` no `radar-dev` primeiro.
3. Opcional: `python manage.py check --deploy` com as variáveis de produção simuladas.

**Migrações incompatíveis** (renomear ou remover campo, tornar obrigatório) em **duas etapas**,
porque o build migra o banco enquanto a versão antiga ainda atende: (1) adicionar o novo campo e
migrar os dados; deploy. (2) remover o antigo; outro deploy.

**Se o build falhar**, o Render cancela o deploy e a versão anterior continua no ar.
**Se o deploy subir com erro**, reverta: `git revert HEAD` e `git push`.

## 4. Administrar a produção

Qualquer comando contra o `radar-prod` roda **do seu computador**, com a variável definida só
naquele terminal (padrão da seção 2.4):

| Tarefa | Comando (depois de `$env:DATABASE_URL = Read-Host ...`) |
|---|---|
| Esqueci a senha (não há e-mail: SMTP é bloqueado no Free) | `python manage.py changepassword <usuario>` |
| Desbloquear login (axes) | `python manage.py axes_reset` |
| Ver migrações aplicadas | `python manage.py showmigrations` |

Sempre termine com `Remove-Item Env:DATABASE_URL`.

**Primeiro acesso lento:** depois de 15 minutos sem uso, o Render hiberna o serviço e o primeiro
acesso leva cerca de 1 minuto. É esperado; não use "pingers" para mantê-lo acordado (consumiriam
as horas do plano e manteriam o banco ligado).

## 5. Backup e restauração

**Fazer backup** (semanal, no mínimo): *Meus dados* → **Baixar backup**. O arquivo JSON contém
seus dados de trabalho e o *hash* da senha: guarde em pasta pessoal protegida, nunca em e-mail ou chat.
O Neon Free só restaura as últimas 6 horas; o backup JSON é a sua cópia de segurança real.

**Restaurar** em um banco **vazio** (projeto ou branch novo no Neon):

```powershell
$env:DATABASE_URL = Read-Host "DATABASE_URL do banco vazio"
python manage.py migrate
python manage.py loaddata caminho\radar-backup-AAAAMMDD.json
Remove-Item Env:DATABASE_URL
```

A restauração é coberta por teste automatizado (`contas/tests/test_dados.py`).
Para trocar a produção pelo banco restaurado, atualize `DATABASE_URL` no painel do Render.

## 6. Resposta a incidente

Suspeita de vazamento (senha do banco ou `SECRET_KEY` em commit/chat, acesso estranho, perda do backup):

1. **Banco:** Neon → `radar-prod` → **Roles** → *Reset password*. Atualize `DATABASE_URL` no Render.
2. **SECRET_KEY:** Render → serviço → *Environment* → gere um novo valor. Todas as sessões caem.
3. **Sua senha:** troque em *Trocar senha* (ou pelo `changepassword`, seção 4).
4. **Acessos:** revise no admin as tentativas de login (Axes) e, no GitHub, quem tem acesso ao repositório.
5. **Segredo em commit:** trocar o segredo resolve; reescrever o histórico do git não basta.
6. **Comunique o encarregado de dados (DPO) da empresa**, que avalia a comunicação à ANPD e aos
   titulares (LGPD, art. 48).

## 7. Limites do plano gratuito

Conferidos em 19/10/2026; podem mudar.

- **Render Free:** hiberna após 15 min; 750 h/mês por workspace; 0,1 CPU e 512 MB; disco efêmero;
  sem Shell; SMTP bloqueado; pode reiniciar a qualquer momento. Login um pouco lento é esperado
  (o hash de senha é pesado de propósito).
- **Neon Free:** 100 CU-hora e 1 GB por projeto por mês; pausa após 5 min sem consultas; PITR de 6 h.

Se as regras mudarem: faça backup e migre para outro PostgreSQL (é PostgreSQL padrão).

## 8. Estrutura do código

| Pasta | Conteúdo |
|---|---|
| `config/` | settings (via variáveis de ambiente), rotas, WSGI |
| `core/` | relógio único (`relogio.py`), IP real (`rede.py`), middlewares (`/saude`, CSP), páginas de erro, filtro de logs |
| `contas/` | usuário, login, privacidade, exportação, backup, "apagar tudo", retenção |
| `demandas/` | modelos, transições (`transicoes.py`), regras (`services.py`), consultas (`selectors.py`), aviso de CPF, CSV |
| `painel/` | Top 3 (`FocoDoDia`), painel do dia, resumo do período (`indicadores.py`) |
| `templates/`, `static/` | telas, CSS/JS próprios e Bootstrap local |

Regras de negócio ficam em `services.py`, consultas em `selectors.py` e as views só orquestram.

## 9. Ideias futuras

Fora do escopo da v1:

- Módulo de e-mails e circulares: resumo, "muda procedimento?", ciência e checklist diário.
- Aprendizados dos cursos ligados às demandas.
- Modo foco (Pomodoro).
- Acesso de leitura para o gestor.
- Integração com Outlook, Gmail, Teams ou WhatsApp; notificações; anexos; app mobile; IA.
- Busca ignorando acentos (extensão `unaccent` do PostgreSQL).
- Cadastro de categorias fora do admin.
