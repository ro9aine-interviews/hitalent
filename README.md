# hitalent

Test task for Python Developer Hitalent.

## Run with Docker Compose

```powershell
docker compose up --build
```

API: http://localhost:8000

Docker Compose starts:

- `api` FastAPI service
- `db` PostgreSQL service

OpenAPI docs:

- http://localhost:8000/docs
- http://localhost:8000/openapi.json

## Tests

```powershell
poetry run tests
```
