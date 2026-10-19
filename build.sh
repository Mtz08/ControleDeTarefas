#!/usr/bin/env bash
# Build no Render (Linux). Se qualquer passo falhar, o deploy é cancelado
# e a versão anterior continua no ar.
set -o errexit
set -o pipefail

pip install -r requirements.txt
python manage.py collectstatic --no-input
# As migrações rodam no build porque o "pre-deploy command" é pago no Render.
# Mudanças incompatíveis devem ser feitas em duas etapas (veja o README).
python manage.py migrate --no-input
