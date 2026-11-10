# Deployment status (2026-11-10)

| Component | State |
|---|---|
| Database | Neon project `relay` (`plain-poetry-45016432`), PostgreSQL 18.6, `aws-ap-southeast-1`. Roles `relay_owner` and `relay_app` created by SQL; both not superuser, not BYPASSRLS, not in `neon_superuser`. Migrations 0001 to 0039 applied. 84 of 84 tenant tables force RLS. App role sees 0 workspaces without tenant context and cannot delete audit events. |
| API | Render Blueprint `relay`, web service `relay-api` (free, Singapore, embedded worker): https://relay-api-3m85.onrender.com. **Waiting for environment variables** (see below). |
| Web | Vercel project `relay-continuity`: https://relay-continuity-nine.vercel.app. Landing page 200, CSP, X-Frame-Options and HSTS present, sign-in redirects to WorkOS with the production callback. |
| WorkOS | Staging environment; production callback `https://relay-continuity-nine.vercel.app/callback` added. |
| GitHub | `main` pushed. `production` environment holds `RELAY_MIGRATION_DATABASE_URL` and `RELAY_BACKUP_PASSPHRASE`; repository secret `RELAY_OPS_TOKEN`; variables `RELAY_API_URL`, `RELAY_WEB_URL` (Monitor workflow active). |
| Secrets | Kept only in git-ignored `deploy/.env.production` and `deploy/.env.render`; never committed or printed. |

## Remaining owner step

Render environment variables must be entered by the account owner (automation is not
permitted to type secrets into the Render dashboard or to mint a Render API key):

1. Render → `relay-backend` environment group → **Add from .env** → paste the contents of
   `deploy/.env.render` → Save. Render redeploys `relay-api`.
2. Check https://relay-api-3m85.onrender.com/health/ready returns 200, then sign in at
   https://relay-continuity-nine.vercel.app.

## Known limits of the pilot setup

* Free Render instance sleeps after 15 idle minutes (the Monitor pings every 10). Production:
  Starter API plus the separate `relay-worker` (about $14 per month), see `render.yaml`.
* Email: Render free blocks outbound SMTP; set `RELAY_RESEND_API_KEY` and `RELAY_EMAIL_FROM`
  with a verified sender to enable it.
* GitHub App, Linear and Notion OAuth apps still point at localhost callbacks; update their
  callback and webhook URLs to the Render and Vercel hosts before connecting real accounts.
* Gemini keys are on Google's unpaid tier, whose terms allow Google to use submitted content.
  Use synthetic data only until a paid tier is enabled.
