# FastAPI layers

Read this from `/architecture` step 3 when the service is FastAPI. The
templated `backend/` from `/setup-project` and `/fastapi-setup` is the
starting point; these are the seams it grows into.

## The three seams

```text
backend/
├── main.py          # app, middleware, router registration — wiring only
├── routers/         # HTTP surface: paths, status codes, Depends
├── schemas/         # Pydantic request/response models
├── services/        # business logic — no FastAPI imports
├── repositories/    # data access: DB, external APIs, cache
└── tests/           # mirrors routers/ and services/
```

The shipped template is a single `main.py` with `/health`. That is
correct until there is a **second** router — split then, not before.
Creating five empty packages around one endpoint is drift in the other
direction.

| Layer | May depend on | Must not |
|---|---|---|
| **Router** | schemas, services, `Depends` providers | run a query, hold business rules, build responses by hand |
| **Service** | repositories, domain types | import `fastapi`, raise `HTTPException`, read `Request` |
| **Repository** | the DB session, `httpx`, SDK clients | know about HTTP status codes |
| **Schema** | nothing | expose an ORM row or a DB column name straight out |

`Depends` is the DI container. Do not add a second one.

## Review the changed files for

- **Fat route functions.** A body past ~20 lines, or containing a query
  or a third-party call, belongs in a service. The route should read as:
  validate, call one service, return.
- **`HTTPException` from a service.** Services raise domain errors; the
  router or an exception handler maps them to status codes. Otherwise
  the logic cannot be reused off an HTTP path.
- **Missing `response_model`.** The contract check in the skill's step 4
  needs a declared shape to compare the Dart API model against. An
  undeclared response is an undocumented breaking change waiting to
  happen.
- **A changed response shape with no Dart-side change in the same
  branch.** This is the high-risk case in `/pr-review`.
- **`Depends(verify_app_check)`** on every route the Flutter client
  calls. Truly public routes go without it, deliberately. `/app-check`
  owns turning enforcement on; the flag default stays `false` in
  `sample.env`.
- **Config read in scattered `os.environ` calls.** Load settings once at
  module scope and inject them.
- **Tests.** New behaviour needs a test under `backend/tests/` using the
  httpx `TestClient`. A route with no test is the same gap as a
  ViewModel with no test.
- **Blocking I/O in an `async def`.** Either make the call async or
  define the endpoint as `def` and let FastAPI use the threadpool.

## Gates

```bash
cd backend
uv run ruff check .
uv run pytest -q
```

Complexity on the Python tree is `/complexity` (`--lang python`, needs
`radon`). CI already runs all three in `python-api.yml`.

## Do not

- Add SQLAlchemy, Alembic or a `repositories/` package to a service with
  no database
- Introduce a DI framework alongside `Depends`
- Repeat App Check logic per route instead of using the one dependency
- Reshape a response "while you are in there" without the client change
