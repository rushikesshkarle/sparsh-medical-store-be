# sparsh-medical-be

FastAPI + MongoDB backend for **Sparsh Medical**. It replaces the Django `products` app
and the Django admin. Same layout as `io-skills-marketplace-be`:
**routes → services → MongoDB**, with shared helpers in `app/shared/`.

```
app/
  main.py                    app factory, lifespan (Mongo connect, indexes), /media static
  core/config.py             settings singleton (env vars)
  api/v1/routes.py           /health + mounts feature routers under /api/v1
  api/v1/auth_routes.py      POST /auth/google, GET /auth/me
  api/v1/product_routes.py   public /products…, admin /admin/products…
  models/                    Pydantic request/response models
  services/                  business logic; the only layer touching MongoDB / disk
  shared/                    constants, messages, CustomResponse, raise_custom_error,
                             ExceptionFilter, security (JWT + user/admin guards), db_connections/mongo.py
scripts/migrate_from_django.py   one-off import from the Django db.sqlite3 + media/
```

Every response is the envelope `{status_code, message, result}`; every error is
`{status_code, message, error}` (422 → `error: [{field, msg}]`).

## API

| Method | Path | Auth |
|---|---|---|
| GET | `/api/v1/health` | — |
| POST | `/api/v1/auth/google` `{code}` (Google popup auth code) → `{access_token, user{…, is_admin}}` | — |
| GET | `/api/v1/auth/me` | Bearer (any user) |
| GET | `/api/v1/products?q=&category=&sort=newest\|price_asc\|price_desc&in_stock=true&page=&page_size=` | — (available only) |
| GET | `/api/v1/products/categories` | — |
| GET | `/api/v1/products/{id}` | — |
| GET | `/api/v1/admin/products?status=all\|live\|hidden\|low_stock&sort=…` / `/{id}` | Admin (incl. hidden) |
| GET | `/api/v1/admin/products/stats` → `{total, live, hidden, low_stock, out_of_stock}` | Admin |
| POST | `/api/v1/admin/products` (multipart: fields + `image`) | Admin |
| PUT | `/api/v1/admin/products/{id}` (multipart; only sent fields change; `remove_image=true`) | Admin |
| DELETE | `/api/v1/admin/products/{id}` | Admin |
| GET | `/api/v1/cart` → `{items: [{id, name, price, quantity, image_url, in_stock}]}` (live prices) | Bearer (any user) |
| PUT | `/api/v1/cart` `{items: [{id, quantity}]}` — replaces the saved cart | Bearer (any user) |

**Admin** = signed in with a Google account whose email is in `ALLOWED_ADMIN_EMAILS`
(checked on every request; a signed-in customer gets 403).

Docs: `http://localhost:8000/api/docs` (hidden when `APP_ENV=production`).

## Run locally

```bash
cp .env.example .env          # set GOOGLE_CLIENT_ID/SECRET and ALLOWED_ADMIN_EMAILS
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
— admins sign in with Google and are listed in `ALLOWED_ADMIN_EMAILS`.

## Production notes

- `APP_ENV=production` refuses to start unless `JWT_SECRET_KEY` is 32+ random characters.
- Product images live on disk in `MEDIA_DIR`; mount a **persistent volume** there
  (compose does). On hosts with an ephemeral disk, use a volume/disk add-on.
- Set `CORS_ALLOW_ORIGINS` to the frontend's origin(s) if it calls the API cross-origin.
- `APP_ENV=production` also requires `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.
- Add or remove admins by editing `ALLOWED_ADMIN_EMAILS` and restarting; no database change needed.
