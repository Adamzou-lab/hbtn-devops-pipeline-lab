# Staging deployment

## Target and trigger

The disposable staging service is **hbtn-pipeline-lab-staging**, hosted by Render
in Frankfurt on the Free plan:
https://hbtn-pipeline-lab-staging.onrender.com

Only a push to `main` can publish or deploy. The workflow orders jobs as
`test -> build -> deploy` through `needs`. A pull request runs tests, lint and
report upload, but skips publication and deployment. Failed tests block both
downstream jobs. Deployment failures fail the workflow instead of being ignored.

The build publishes the runtime Docker stage to GHCR under two tags:

- `ghcr.io/adamzou-lab/hbtn-devops-pipeline-lab:<full-commit-SHA>` identifies the
  source revision and is the tag used by the deploy job.
- `ghcr.io/adamzou-lab/hbtn-devops-pipeline-lab:latest` moves on each successful
  build. It is convenient for local smoke tests, not for selecting a rollback.

GitHub repository names are normalized to lowercase for Docker. The package is
public by an explicit lab choice: the runtime image contains only the supplied
public application, dependency manifests and production dependencies. It has no
database URL, account token or populated environment file. Render therefore
needs no registry credential to pull it. `packages: write` is granted only to
the build job; publication uses the ephemeral `GITHUB_TOKEN` and no PAT.

## Database and configuration

The dedicated Render PostgreSQL database is **hbtn-pipeline-lab-db**, also in
Frankfurt. Its generated internal connection URL is stored only as the service's
`DATABASE_URL` environment variable. The application runs its supplied
idempotent migrations and seeds on startup. No local database volume is used
by staging. The Free database expires on **2026-10-25**; this is a temporary lab.

Repository Actions settings:

| Setting | Storage | Purpose |
| --- | --- | --- |
| `RENDER_API_KEY` | GitHub Actions secret | Authenticate deployment requests |
| `RENDER_SERVICE_ID` | GitHub Actions secret | Select the lab web service |
| `STAGING_URL` | Repository variable | HTTPS URL above, without a trailing slash |

The API key must be created under Render account settings and stored directly
in `RENDER_API_KEY`. Render's account API-key form does not offer a per-service
scope, so access to this secret must be restricted and the key revoked after
the lab. It must never appear in a commit, image, log or deployment document.
CI's `pipeline` database username/password are disposable starter fixtures for
the runner's PostgreSQL container, not credentials for any external account.

## Deployment and verification

`scripts/deploy_render.py` posts to
`https://api.render.com/v1/services/<service-id>/deploys`, passing the exact SHA
image as `imageUrl`. It waits for that deployment ID to become `live` and fails
on a failed/canceled deployment or deadline. Only then does it check both
`/health` and `/items` with bounded retries. Both must return HTTP 200 in the
same verification round. Render's own service health-check path is `/items`.

Independent checks, outside GitHub Actions:

```sh
curl --fail --show-error https://hbtn-pipeline-lab-staging.onrender.com/health
curl --fail --show-error https://hbtn-pipeline-lab-staging.onrender.com/items
```

The first initial deployment was independently verified on 2026-09-25:
`/health` returned HTTP 200 with `{"status":"ok"}`; `/items` returned HTTP 200
with the seeded Alpha and Beta items. The initial image was
`4c3cd1af87c4badb3ec17bde9f45674252ecb8b6`.

`/health` is liveness only and does not touch PostgreSQL. `/items` adds evidence
that the current instance can query its database. A green pipeline establishes
that these checks and the supplied tests passed for a revision; it does not
prove the absence of security flaws, exhaustive correctness or future uptime.
Free Render instances may sleep, so verification allows startup time.

## Rollback

Select a previously successful full commit tag in GHCR and record its digest.
In this Render service, edit **Settings -> Image -> Source**, keeping the same
repository but replacing the tag with that known-good SHA, then use
**Manual Deploy -> Deploy latest reference**. Alternatively,
trigger the same deployment API with `imageUrl` set to that SHA tag. Wait for
the new deployment to become live, then check both endpoints again. Do not use
`latest` to choose the old revision. Keep the SHA tags intact; registry tags are
technically mutable, while a recorded digest identifies the exact image.

For a source-level regression, revert the offending commit and push the revert
to `main`; tests, publication and deployment run again. An image rollback does
not undo database schema or data changes. This lab's existing migrations are
idempotent; a future incompatible migration would need its own rollback plan.

## Cleanup

After evaluation, stop or delete only **hbtn-pipeline-lab-staging** and
**hbtn-pipeline-lab-db** in Render, revoke the dedicated API key, and remove the
repository secrets/variable. Database deletion permanently removes its lab
data. Retain any evidence needed for evaluation first. Do not touch other
Render services. Locally, `docker compose down -v` removes the disposable stack
and database volume; the separate GHCR smoke-test container is also stopped.
