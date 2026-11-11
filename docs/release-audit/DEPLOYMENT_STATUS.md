# Deployment status (2026-11-11)

| Component | State |
|---|---|
| Database | Neon project `relay` (`plain-poetry-45016432`), PostgreSQL 18.6, `aws-ap-southeast-1`. Roles `relay_owner` and `relay_app` created by SQL; both not superuser, not BYPASSRLS, not in `neon_superuser`. Migrations 0001 to 0039 applied. 84 of 84 tenant tables force RLS. App role sees 0 workspaces without tenant context and cannot delete audit events. |
| API | Render Blueprint `relay`, web service `relay-api` (free, Singapore, embedded worker): https://relay-api-3m85.onrender.com. Environment configured, including GitHub, Linear and Notion connectors; `/health/ready` returns 200. |
| Web | Vercel project `relay-continuity`: https://relay-continuity-nine.vercel.app. Landing page 200, CSP, X-Frame-Options and HSTS present, sign-in redirects to WorkOS with the production callback. |
| WorkOS | Staging environment; production callback `https://relay-continuity-nine.vercel.app/callback` added. |
| GitHub | `main` pushed. `production` environment holds `RELAY_MIGRATION_DATABASE_URL` and `RELAY_BACKUP_PASSPHRASE`; repository secret `RELAY_OPS_TOKEN`; variables `RELAY_API_URL`, `RELAY_WEB_URL` (Monitor workflow active). |
| Secrets | Kept only in git-ignored `deploy/.env.production` and `deploy/.env.render`; never committed or printed. |

## Changes on 2026-11-11

* Vercel project Root Directory set to `frontend`. Git-triggered builds had failed since
  2026-11-10 because Vercel built from the repository root; pushes to `main` now deploy.
* Connector credentials added to the Render `relay-backend` environment group; production
  callback URLs registered for the GitHub App, Linear and Notion OAuth apps.
* `POST /workspaces/sample` lets a signed-in user create the synthetic "Northwind Labs
  (demo)" workspace without command-line access (`RELAY_SAMPLE_WORKSPACES`).

## Known limits of the pilot setup

* Free Render instance sleeps after 15 idle minutes (the Monitor pings every 10). Production:
  Starter API plus the separate `relay-worker` (about $14 per month), see `render.yaml`.
* Email: Render free blocks outbound SMTP; set `RELAY_RESEND_API_KEY` and `RELAY_EMAIL_FROM`
  with a verified sender to enable it.
* Gemini keys are on Google's unpaid tier, whose terms allow Google to use submitted content.
  Use synthetic data only until a paid tier is enabled.
