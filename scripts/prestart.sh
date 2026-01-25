#! /usr/bin/env bash

set -e
set -x

echo "Let the DB start"
poetry run python -m app.backend_pre_start

echo "Run migrations"
poetry run alembic revision --autogenerate -m "New Migration"

echo "Upgrade migrations"
poetry run alembic upgrade head
