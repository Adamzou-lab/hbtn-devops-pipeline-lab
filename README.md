# hbtn-devops-pipeline-lab

[![CI](https://github.com/Adamzou-lab/hbtn-devops-pipeline-lab/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/Adamzou-lab/hbtn-devops-pipeline-lab/actions/workflows/ci.yml?query=branch%3Amain)

This repository contains the application used in the **CI/CD Pipeline Essentials** lab. It is a small Express API backed by PostgreSQL. The application and tests are already implemented; your work is to diagnose and extend its delivery pipeline.

The original workflow's three intentional faults were diagnosed from real failed runs and repaired in three separate `fix(ci)` commits. The workflow now runs lint and all 11 tests, retains JUnit reports, caches npm downloads, and publishes a tested production image to GHCR on successful pushes to `main`.

See [DEPLOY.md](DEPLOY.md) for the staging target, credentials, readiness checks, rollback and cleanup. [local_verify.txt](local_verify.txt) records the local container baseline.

## Repository contents

```text
src/
  server.js                       Express app, routes, and error handling
  routes/health.js                GET /health
  routes/items.js                 GET /items, POST /items, and input validation
  db/connection.js                lazy PostgreSQL pool built from DATABASE_URL
  db/migrate.js                   idempotent migration runner
  db/migrations/*.sql             schema and seed data
tests/
  unit/health.test.js             3 unit tests
  unit/items.unit.test.js         5 unit tests
  integration/items.int.test.js  3 integration tests that require PostgreSQL
Dockerfile                        builder and production runtime stages
docker-compose.yml                local app and database services
jest.config.js                    Jest configuration; CI enables JUnit via CLI
.eslintrc.json                    lint rules used by npm run lint
.github/workflows/ci.yml          test, image publication and staging deployment
scripts/deploy_render.py         bounded deployment and readiness verification
```

The test suite contains 11 deterministic tests: 8 unit tests and 3 integration tests. Unit tests need only Node.js. Integration tests need a reachable PostgreSQL database.

## API

| Method | Path | Behavior |
|---|---|---|
| `GET` | `/health` | Returns `200` with `{"status":"ok"}`. This is a liveness check and does not query the database. |
| `GET` | `/items` | Returns `200` with stored items ordered by creation. This route requires the database. |
| `POST` | `/items` | Creates an item and returns `201`, or returns `400` when `name` is invalid. |

The application listens on port `3000`. Database operations read the connection string from `DATABASE_URL`; there is no built-in fallback.

## Run the application in containers

You do not need Node.js or npm on the host. Run the supplied commands inside the containers:

```bash
docker compose up -d
docker compose ps

docker compose run --rm app npm run test:unit
docker compose run --rm app npm run test:integration
docker compose run --rm app npm test
docker compose run --rm app npm run lint

curl -s http://localhost:3000/health
curl -s http://localhost:3000/items
curl -s -X POST http://localhost:3000/items \
  -H 'Content-Type: application/json' \
  -d '{"name":"Delta Item"}'

docker compose down -v
```

The Compose `app` service targets the `builder` stage, which includes Jest, Supertest, and ESLint. The pipeline builds the smaller `runtime` stage for deployment.

## Pipeline repair evidence

| Failure observed | Focused repair | Evidence |
| --- | --- | --- |
| Invalid workflow YAML | Correct `steps` indentation (`79184db`) | [Initial parser failure](https://github.com/Adamzou-lab/hbtn-devops-pipeline-lab/actions/runs/36164109212) |
| Unknown command `install-deps` | Use the lockfile with `npm ci` (`64f5171`) | [Runner failure](https://github.com/Adamzou-lab/hbtn-devops-pipeline-lab/actions/runs/36164379292) |
| `DATABASE_URL is not set` | Provide the CI service connection in workflow env (`2adcdc5`) | [Integration failure](https://github.com/Adamzou-lab/hbtn-devops-pipeline-lab/actions/runs/36164541991) |

The [repaired test job](https://github.com/Adamzou-lab/hbtn-devops-pipeline-lab/actions/runs/36164671856) passed. The [first cache run](https://github.com/Adamzou-lab/hbtn-devops-pipeline-lab/actions/runs/36165009427) saved npm downloads; the [second run](https://github.com/Adamzou-lab/hbtn-devops-pipeline-lab/actions/runs/36165246181) restored the exact same lockfile key. Both passed lint and 11 tests and uploaded JUnit reports for seven days. The cache contains downloads, not `node_modules`; `npm ci` still installs the reviewed dependency tree each time.

The [publication PR](https://github.com/Adamzou-lab/hbtn-devops-pipeline-lab/pull/1) passed tests with build skipped. Its [merge run](https://github.com/Adamzou-lab/hbtn-devops-pipeline-lab/actions/runs/36165631599) built and published the runtime image, which was independently pulled and verified locally on `/health`.

## Troubleshooting

| Symptom | What to check |
|---|---|
| `DATABASE_URL is not set` | Run through Docker Compose locally, or provide the connection string in the environment that executes integration tests or the deployed API. |
| Integration tests cannot connect | Confirm that the database is healthy with `docker compose ps`. |
| Changes to `package.json` are ignored | Recreate the development volume with `docker compose down -v`, then rebuild. |
| `npm ci` reports a lock-file mismatch | Regenerate dependencies inside the container, review the lock-file change, and commit both manifests. |
| Port `3000` is already in use | Stop the process using the port or change the published host port in `docker-compose.yml`. |

## License

This lab is distributed under the MIT License. See `LICENSE`.
