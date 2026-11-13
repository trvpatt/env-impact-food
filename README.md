# Rooted

A plant-forward web app that tracks the health and environmental impact of your food choices and helps you find recipes, restaurants, local produce and community initiatives.

`openapi.yaml` is the API contract. Backend models are generated from it.

```
openapi.yaml          API contract (source of truth)
backend/
  app/
    core/             config, DB session, security, errors, pagination
    models/           database tables (SQLModel)
    schemas/          generated API models (do not edit)
    routers/          one file per OpenAPI tag
    services/         business logic and backing-service clients
  migrations/         Alembic migrations
  scripts/            admin tasks (reference-data seeding)
  tests/
  Dockerfile
infra/                docker-compose dev stack (Postgres, Mailpit, API)
data_pipeline/        OWID / USDA data exploration
frontend/             JavaScript web client
```

## Run locally

```sh
python3.13 -m venv myenv
myenv/bin/pip install -r backend/requirements-dev.txt
cp .env.example .env            # then set JWT_SECRET
docker compose -f infra/docker-compose.yml up -d db mail

cd backend
../myenv/bin/alembic upgrade head
../myenv/bin/python -m scripts.seed_reference_data
../myenv/bin/uvicorn app.main:app --reload
```

- API docs: http://localhost:8000/api/v1/docs
- Captured emails (sign-up, password reset): http://localhost:8025

## Test

```sh
myenv/bin/pytest
```

## Changing the API

1. Edit `openapi.yaml`, then validate it: `myenv/bin/openapi-spec-validator openapi.yaml`
2. Regenerate the models (see `CLAUDE.md`) and commit them with the spec change.
3. Implement the change in `routers/` and `services/`.
4. If tables change, add a migration: `cd backend && ../myenv/bin/alembic revision --autogenerate -m "..."`
