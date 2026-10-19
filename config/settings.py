"""Configurações do Radar de Demandas.

Tudo que muda entre o seu computador e a produção vem de variáveis de ambiente.
Localmente elas são lidas do arquivo .env; no Render, do painel do serviço.
Uma variável definida no próprio terminal tem prioridade sobre o .env.
"""

import os
import sys
from datetime import timedelta
from pathlib import Path

import dj_database_url
from django.contrib.messages import constants as messages
from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


def _obrigatoria(nome: str) -> str:
    """Lê uma variável de ambiente que precisa existir e não pode ser vazia."""
    valor = os.environ.get(nome, "").strip()
    if not valor:
        raise ImproperlyConfigured(f"Defina a variável de ambiente {nome} (veja .env.example).")
    return valor


def _booleana(nome: str, padrao: bool = False) -> bool:
    valor = os.environ.get(nome)
    if valor is None:
        return padrao
    return valor.strip().lower() in {"1", "true", "sim", "yes", "on"}


def _lista(nome: str) -> list[str]:
    return [item.strip() for item in os.environ.get(nome, "").split(",") if item.strip()]


TESTANDO = len(sys.argv) > 1 and sys.argv[1] == "test"

# --- Núcleo -------------------------------------------------------------------

SECRET_KEY = _obrigatoria("SECRET_KEY")
DEBUG = _booleana("DEBUG")

ALLOWED_HOSTS = _lista("ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS: list[str] = []

# O Render informa o domínio público do serviço nesta variável.
RENDER_EXTERNAL_HOSTNAME = os.environ.get("RENDER_EXTERNAL_HOSTNAME", "").strip()
if RENDER_EXTERNAL_HOSTNAME:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)
    CSRF_TRUSTED_ORIGINS.append(f"https://{RENDER_EXTERNAL_HOSTNAME}")

ADMIN_URL = os.environ.get("ADMIN_URL", "admin/").strip().strip("/") + "/"
if not DEBUG and not TESTANDO and ADMIN_URL == "admin/":
    raise ImproperlyConfigured("Em produção, defina ADMIN_URL com um caminho difícil de adivinhar.")

# Quantos proxies confiáveis ficam na frente do app (Render: 1). Localmente, 0.
# Usado para descobrir o IP real do cliente sem confiar em cabeçalho forjado.
PROXIES_CONFIAVEIS = int(os.environ.get("PROXIES_CONFIAVEIS", "0"))

# --- Aplicações ---------------------------------------------------------------

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "whitenoise.runserver_nostatic",
    "django.contrib.staticfiles",
    "axes",
    "core",
    "contas",
    "demandas",
    "painel",
]

MIDDLEWARE = [
    # Primeiro da pilha: /saude responde sem HTTPS, sem validar Host e sem banco.
    "core.middleware.SaudeMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "core.middleware.CabecalhosSegurancaMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    # Toda página exige login, exceto as marcadas com @login_not_required.
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # O django-axes recomenda ficar por último.
    "axes.middleware.AxesMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "demandas.context_processors.captura",
            ],
        },
    },
]

# --- Banco de dados (PostgreSQL no Neon) --------------------------------------

DATABASES = {
    "default": dj_database_url.parse(
        _obrigatoria("DATABASE_URL"),
        # Reaproveita a conexão por até 60 s; o health check reconecta se o Neon
        # tiver pausado e fechado a conexão nesse meio-tempo.
        conn_max_age=60,
        conn_health_checks=True,
        ssl_require=True,
    )
}
# O Neon pode levar alguns instantes para "acordar" (cold start).
DATABASES["default"].setdefault("OPTIONS", {})["connect_timeout"] = 10

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- Autenticação e sessão ----------------------------------------------------

AUTH_USER_MODEL = "contas.Usuario"

AUTHENTICATION_BACKENDS = [
    # O axes vem antes: bloqueia a tentativa antes de conferir a senha.
    "axes.backends.AxesStandaloneBackend",
    "django.contrib.auth.backends.ModelBackend",
]

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": 12},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LOGIN_URL = "contas:entrar"
LOGIN_REDIRECT_URL = "painel:inicio"
LOGOUT_REDIRECT_URL = "contas:entrar"

SESSION_COOKIE_AGE = int(timedelta(hours=12).total_seconds())
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

# django-axes: 5 erros seguidos do mesmo usuário no mesmo IP bloqueiam por 30 min.
# A combinação usuário + IP evita que um terceiro bloqueie você de qualquer lugar.
AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = timedelta(minutes=30)  # também faz o axes apagar tentativas expiradas
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
AXES_DISABLE_ACCESS_LOG = True  # não guarda histórico de logins bem-sucedidos (minimização)
AXES_CLIENT_IP_CALLABLE = "core.rede.ip_do_cliente"
AXES_LOCKOUT_TEMPLATE = "contas/bloqueado.html"

if TESTANDO:
    # Hash rápido só nos testes; em produção vale o padrão (lento de propósito).
    PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# --- Segurança HTTP -----------------------------------------------------------

X_FRAME_OPTIONS = "DENY"
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True

if not DEBUG:
    # O Render termina o HTTPS no proxy e avisa o protocolo original neste cabeçalho.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = not TESTANDO
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    # HSTS começa baixo (1 h); depois de validado, suba via variável (ex.: 31536000).
    SECURE_HSTS_SECONDS = int(os.environ.get("HSTS_SEGUNDOS", "3600"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True

# security.W021 (HSTS preload) silenciado de propósito: entrar na lista de preload
# dos navegadores é praticamente irreversível e o site usa um subdomínio do Render.
SILENCED_SYSTEM_CHECKS = ["security.W021"]

# --- Idioma e fuso ------------------------------------------------------------

LANGUAGE_CODE = "pt-br"
TIME_ZONE = "America/Sao_Paulo"
USE_I18N = True
USE_TZ = True

# --- Arquivos estáticos -------------------------------------------------------

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        # Em produção: nomes com hash (cache seguro) e arquivos comprimidos, gerados no build.
        # Local e nos testes: armazenamento simples, sem precisar rodar collectstatic.
        "BACKEND": (
            "django.contrib.staticfiles.storage.StaticFilesStorage"
            if DEBUG or TESTANDO
            else "whitenoise.storage.CompressedManifestStaticFilesStorage"
        ),
    },
}

# --- Logs ---------------------------------------------------------------------

# Só no console (o Render coleta). O filtro remove detalhes de erros de banco,
# que podem conter o conteúdo das demandas.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"sem_dados": {"()": "core.logs.SemDadosDoBancoFilter"}},
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["sem_dados"],
        },
    },
    "root": {"handlers": ["console"], "level": "WARNING"},
    "loggers": {
        "django": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "axes": {"handlers": ["console"], "level": "WARNING", "propagate": False},
    },
}

# --- Mensagens ----------------------------------------------------------------

# "error" vira "danger" para casar com as classes de alerta do Bootstrap.
MESSAGE_TAGS = {messages.ERROR: "danger"}

# --- Regras do domínio --------------------------------------------------------

# Meses após a conclusão/cancelamento para uma demanda aparecer na tela de retenção.
RETENCAO_MESES = int(os.environ.get("RETENCAO_MESES", "12"))
