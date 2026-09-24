#!/usr/bin/env bash
set -euo pipefail
python manage.py collectstatic --noinput
python manage.py migrate
