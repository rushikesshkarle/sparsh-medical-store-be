# sparsh-medical-be

FastAPI + MongoDB backend for **Sparsh Medical**. It replaces the Django `products` app
and the Django admin. Same layout as `io-skills-marketplace-be`:
**routes → services → MongoDB**, with shared helpers in `app/shared/`.

```
app/
  main.py                    app factory, lifespan (Mongo connect, indexes), /media static
  core/config.py             settings singleton (env vars)
  api/v1/routes.py           /health + mounts feature routers under /api/v1
  api/v1/auth_routes.py      POST /auth/login, GET /auth/me
  api/v1/product_routes.py   public /products…, admin /admin/products…
  models/                    Pydantic request/response models
  services/                  business logic; the only layer touching MongoDB / disk
  shared/                    constants, messages, CustomResponse, raise_custom_error,
                             ExceptionFilter, security (JWT + admin guard), db_connections/mongo.py
scripts/migrate_from_django.py   one-off import from the Django db.sqlite3 + media/
```

Every response is the envelope `{status_code, message, result}`; every error is
`{status_code, message, error}` (422 → `error: [{field, msg}]`).

## API

| Method | Path | Auth |
|---|---|---|
| GET | `/api/v1/health` | — |
| POST | `/api/v1/auth/login` `{username, password}` → `{access_token, admin}` (5 failures / 15 min per IP → 429) | — |
| GET | `/api/v1/auth/me` | Admin |
| GET | `/api/v1/products?q=&category=&sort=newest\|price_asc\|price_desc&in_stock=true&page=&page_size=` | — (available only) |
| GET | `/api/v1/products/categories` | — |
| GET | `/api/v1/products/{id}` | — |
| GET | `/api/v1/admin/products?status=all\|live\|hidden\|low_stock&sort=…` / `/{id}` | Admin (incl. hidden) |
| GET | `/api/v1/admin/products/stats` → `{total, live, hidden, low_stock, out_of_stock}` | Admin |
| POST | `/api/v1/admin/products` (multipart: fields + `image`) | Admin |
| PUT | `/api/v1/admin/products/{id}` (multipart; only sent fields change; `remove_image=true`) | Admin |
| DELETE | `/api/v1/admin/products/{id}` | Admin |

**Admin** = Bearer token from `POST /auth/login` with `ADMIN_USERNAME` / `ADMIN_PASSWORD`
from the env. There are no customer accounts; shoppers order on WhatsApp as guests.

Docs: `http://localhost:8000/api/docs` (hidden when `APP_ENV=production`).

## Run locally

```bash
cp .env.example .env          # set ADMIN_PASSWORD
poetry install
poetry run uvicorn app.main:app --reload
```

or with Docker (backend + MongoDB, persistent volumes for data and images):

```bash
docker compose up --build     # API on :8000, Mongo on 127.0.0.1:27019
```

## Migrating data from the Django site

```bash
poetry run python -m scripts.migrate_from_django \
  --sqlite /path/to/backend/db.sqlite3 --media /path/to/backend/media
```

Idempotent (skips products already imported). Django admin users are **not** migrated
— the admin logs in with `ADMIN_USERNAME` / `ADMIN_PASSWORD`.

## Production notes

- `APP_ENV=production` refuses to start unless `JWT_SECRET_KEY` is 32+ random characters.
- Product images are resized to 1200px and stored as WebP. With `CLOUDINARY_*` set they
  go to Cloudinary (use this on Render free, whose disk is wiped on restart); otherwise
  they live on disk in `MEDIA_DIR` — mount a **persistent volume** there (compose does).
- Public product listings and categories are cached for 60s per worker; admin writes
  clear the cache, so the storefront reflects changes within a minute.
- Set `CORS_ALLOW_ORIGINS` to the frontend's origin(s) if it calls the API cross-origin.
- `APP_ENV=production` also requires an `ADMIN_PASSWORD` of 12+ characters.
- Change the admin password by editing `ADMIN_PASSWORD` and restarting; every existing
  admin session is signed out.
