# Environment setup: every variable, where it comes from

Relay reads its settings from environment files that are **never committed**. This guide
covers the three places they live and, for each value, where to get it.

| File / place | Used by | Template |
|---|---|---|
| `backend/.env` | API and worker on your machine | `backend/.env.example` |
| `frontend/.env.local` | Web app on your machine | `frontend/.env.example` |
| Render, Vercel and GitHub settings | Production | `deploy/.env.production.example` (names and descriptions only) |

Rules: copy the template, fill it in, keep it local. Never paste real values into chat, git,
issues or screenshots. Each developer uses their **own** development keys; production values
live only in Render, Vercel and the GitHub `production` environment. Dashboards change their
menus from time to time: if a button below has moved, the page linked is still the right one.

Generate random values with:

```sh
openssl rand -base64 32                       # cookie passwords and similar secrets
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"   # Fernet key
```

(On Windows without openssl: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.)

---

## 1. Local development (minimum to run)

You need Docker, `uv`, `pnpm` and a free WorkOS account. Everything else is optional.

### 1.1 Database: nothing to sign up for

`docker compose up -d --wait` starts Postgres and creates the `relay_owner` and `relay_app`
roles. The values already in `backend/.env.example` match it:

```
RELAY_ENVIRONMENT=local
RELAY_DATABASE_URL=postgresql+psycopg://relay_app:relay_app_dev@localhost:5432/relay
RELAY_MIGRATION_DATABASE_URL=postgresql+psycopg://relay_owner:relay_owner_dev@localhost:5432/relay
RELAY_APP_DB_ROLE=relay_app
RELAY_FRONTEND_BASE_URL=http://localhost:3000
RELAY_EMBEDDED_WORKER=true      # add this: runs background jobs inside the API locally
```

### 1.2 WorkOS (sign-in): required

1. Sign up at <https://dashboard.workos.com/signup> and open the **Staging** environment
   (switcher at the top left). Use Staging for development, never Production.
2. Left menu **Authentication** (or **User Management**) → enable **AuthKit** and the sign-in
   methods you want (Email + one-time code is enough).
3. Left menu **Redirects**:
   - **Redirect URI**: `http://localhost:3000/callback` (set it as default)
   - **Sign-in endpoint / Initiate login URL**: `http://localhost:3000/sign-in`
   - **Sign-out redirect**: `http://localhost:3000/`
4. Left menu **API Keys**: copy the **Client ID** (`client_…`) and the **Secret Key**
   (`sk_test_…`).
5. Fill in:

   `backend/.env`
   ```
   RELAY_WORKOS_CLIENT_ID=client_…
   RELAY_WORKOS_API_KEY=sk_test_…
   ```
   `frontend/.env.local`
   ```
   WORKOS_CLIENT_ID="client_…"
   WORKOS_API_KEY="sk_test_…"
   WORKOS_COOKIE_PASSWORD="<openssl rand -base64 32>"
   NEXT_PUBLIC_WORKOS_REDIRECT_URI="http://localhost:3000/callback"
   WORKOS_ISSUER="https://api.workos.com/user_management/client_…"
   RELAY_API_URL="http://127.0.0.1:8000"
   ```

That's enough to run Relay with the sample workspace. Everything below is optional.

### 1.3 AI (optional)

Without AI, Relay still runs rule-based analysis, briefs and labelled search.

- **Gemini** (recommended, free tier): <https://aistudio.google.com/apikey> → **Create API key**
  → pick or create a Google Cloud project → copy the key.
- **Groq** (optional fallback): <https://console.groq.com/keys> → **Create API Key**.

```
RELAY_LLM_PROVIDERS=gemini            # or gemini,groq
RELAY_GEMINI_KEY_1=…                  # up to 4 keys; Relay moves on when one hits its quota
RELAY_GEMINI_MODEL=gemini-3.5-flash-lite
RELAY_GROQ_API_KEY=…                  # only if groq is listed
```

### 1.4 Encryption key for connector tokens (needed for Linear or Notion)

```
RELAY_INTEGRATION_ENCRYPTION_KEY=<Fernet key from the command above>
```

Keep a copy: if it changes, Linear and Notion must be reconnected.

### 1.5 GitHub App (optional)

1. Open <https://github.com/settings/apps/new> (for an organisation:
   `https://github.com/organizations/<org>/settings/apps/new`).
2. Fill in:
   - **GitHub App name**: e.g. `Relay Dev (yourname)` (must be globally unique)
   - **Homepage URL**: `http://localhost:3000`
   - **Callback URL**: `http://localhost:3000/integrations/github/callback`
   - Tick **Request user authorization (OAuth) during installation**
   - **Webhook**: untick **Active** for local development (use "Sync now" instead)
3. **Permissions**:
   - Repository → **Contents**: Read-only · **Metadata**: Read-only · **Pull requests**:
     Read-only · **Issues**: Read-only
   - Organization → **Members**: Read-only
4. **Where can this GitHub App be installed?** → *Only on this account* → **Create GitHub App**.
5. On the app page:
   - **App ID** → `RELAY_GITHUB_APP_ID`
   - The app's URL `github.com/apps/<slug>` → `RELAY_GITHUB_APP_SLUG`
   - **Client ID** → `RELAY_GITHUB_CLIENT_ID`
   - **Generate a new client secret** → `RELAY_GITHUB_CLIENT_SECRET`
   - **Private keys → Generate a private key** downloads a `.pem` file. Put it in one line with
     `\n` for line breaks, in double quotes:
     `RELAY_GITHUB_PRIVATE_KEY="-----BEGIN RSA PRIVATE KEY-----\nMIIE…\n-----END RSA PRIVATE KEY-----\n"`
6. Restart the API, then in Relay: **Integrations → Connect GitHub**.

### 1.6 Linear (optional)

1. Open <https://linear.app/settings/api/applications/new> (Linear → **Settings** → **API** →
   **OAuth Applications** → **New**).
2. **Application name**: `Relay Dev`; **Developer name / URL**: anything;
   **Callback URLs**: `http://localhost:3000/integrations/linear/callback`.
3. Leave **Webhooks** off. **Create**.
4. Copy **Client ID** and **Client Secret**:
   ```
   RELAY_LINEAR_CLIENT_ID=…
   RELAY_LINEAR_CLIENT_SECRET=…
   RELAY_LINEAR_OAUTH_SCOPE=read
   ```
5. Needs `RELAY_INTEGRATION_ENCRYPTION_KEY` (1.4). Connect from **Integrations → Linear**.

### 1.7 Notion (optional)

1. Open <https://www.notion.so/profile/integrations> → **New integration**.
2. **Type**: **Public** (OAuth). Pick your workspace, give it a name.
3. **Redirect URIs**: `http://localhost:3000/integrations/notion/callback`. Fill in the
   required company / website / privacy fields (your GitHub repo URL is fine for testing).
4. **Capabilities**: tick **Read content** only. No insert or update. **Save**.
5. Copy **OAuth Client ID** and **OAuth Client Secret**:
   ```
   RELAY_NOTION_CLIENT_ID=…
   RELAY_NOTION_CLIENT_SECRET=…
   RELAY_NOTION_PAGE_LIMIT=500
   ```
6. Needs `RELAY_INTEGRATION_ENCRYPTION_KEY`. Connect from **Integrations → Notion** and pick
   the pages Relay may read.

### 1.8 Email (optional)

Without email, notifications stay in the in-app inbox and invitations go through WorkOS.

- **Resend**: <https://resend.com/api-keys> → **Create API Key** (Sending access). For real
  sending, verify a domain at <https://resend.com/domains> (add the SPF and DKIM records it
  shows to your DNS).
  ```
  RELAY_RESEND_API_KEY=re_…
  RELAY_EMAIL_FROM="Relay <notifications@your-domain>"
  ```
- **Gmail SMTP** instead: turn on 2-Step Verification, then <https://myaccount.google.com/apppasswords>
  → create an app password.
  ```
  RELAY_SMTP_HOST=smtp.gmail.com
  RELAY_SMTP_PORT=587
  RELAY_SMTP_SECURITY=starttls
  RELAY_SMTP_USERNAME=you@gmail.com
  RELAY_SMTP_PASSWORD=<16-character app password>
  RELAY_EMAIL_FROM=you@gmail.com
  ```

---

## 2. Production (Neon + Render + Vercel + GitHub Actions)

Production uses **separate** credentials from development: the WorkOS **Production**
environment, a production GitHub App / Linear app / Notion integration whose callback URLs
use the real domain, and new random secrets. Full detail: [deployment.md](../deployment.md).

### 2.1 Neon (database)

1. <https://console.neon.tech> → **New Project** → Postgres **18**, region close to Render
   (e.g. AWS Singapore).
2. **Connection Details** → copy the **direct** (not pooled) connection string for
   `neondb_owner`.
3. Open the **SQL Editor** and run the role SQL in [deployment.md §3.1](../deployment.md)
   with two new strong passwords. Do not create these roles in the console: console roles can
   bypass row-level security.
4. Build the two URLs (`sslmode=require` on both):
   - `RELAY_MIGRATION_DATABASE_URL=postgresql+psycopg://relay_owner:<owner-pw>@<host>/relay?sslmode=require`
   - `RELAY_DATABASE_URL=postgresql+psycopg://relay_app:<app-pw>@<host>/relay?sslmode=require`

### 2.2 GitHub (migrations, purge, keep-warm)

1. Repository → **Settings** → **Environments** → **New environment** → name `production`
   → **Add environment secret** → `RELAY_MIGRATION_DATABASE_URL` = owner URL from 2.1.
   This is the only place the owner credential lives.
2. **Settings** → **Secrets and variables** → **Actions** → **Variables** tab → **New
   repository variable** → `RELAY_API_HEALTH_URL` = `https://<api>.onrender.com/health/live`
   (keeps the free API awake).
3. Run migrations: **Actions** → **Migrate** → **Run workflow** (branch to deploy).

### 2.3 Render (API and worker)

1. <https://dashboard.render.com> → **New** → **Blueprint** → connect the GitHub repo →
   Render reads `render.yaml`.
2. It prompts for every secret. Fill in:

   | Variable | Value |
   |---|---|
   | `RELAY_DATABASE_URL` | app-role URL from 2.1 |
   | `RELAY_FRONTEND_BASE_URL` | `https://<your Vercel domain>` (no trailing slash) |
   | `RELAY_WORKOS_CLIENT_ID`, `RELAY_WORKOS_API_KEY` | WorkOS **Production** → API Keys (`sk_live_…`) |
   | `RELAY_INTEGRATION_ENCRYPTION_KEY` | a new Fernet key; back it up |
   | `RELAY_LLM_PROVIDERS`, `RELAY_GEMINI_KEY_1…4`, `RELAY_GROQ_API_KEY` | optional, as in 1.3 |
   | `RELAY_GITHUB_*`, `RELAY_GITHUB_WEBHOOK_SECRET` | production GitHub App (2.5) |
   | `RELAY_LINEAR_*`, `RELAY_NOTION_*` | production Linear and Notion apps (2.5) |
   | `RELAY_RESEND_API_KEY`, `RELAY_EMAIL_FROM` or `RELAY_SMTP_*` | optional |

3. To change a value later: service → **Environment** → edit → **Save, rebuild and deploy**.
4. Check `https://<api>.onrender.com/health/ready` returns 200.

### 2.4 Vercel (web)

1. <https://vercel.com/new> → import the repo → **Root Directory**: `frontend`.
2. **Settings** → **Functions** → region next to Render (e.g. `sin1`).
3. **Settings** → **Environment Variables**, environment **Production**:

   | Variable | Value |
   |---|---|
   | `RELAY_API_URL` | `https://<api>.onrender.com` |
   | `WORKOS_CLIENT_ID`, `WORKOS_API_KEY` | WorkOS Production |
   | `WORKOS_COOKIE_PASSWORD` | new `openssl rand -base64 32` |
   | `WORKOS_ISSUER` | `https://api.workos.com/user_management/<prod client id>` |
   | `NEXT_PUBLIC_WORKOS_REDIRECT_URI` | `https://<your domain>/callback` |

   Give **Preview** its own non-production values, or turn previews off.
4. **Deployments** → redeploy after changing variables (`NEXT_PUBLIC_*` is baked in at build).

### 2.5 Production callback URLs to register

| Service | Where | URL |
|---|---|---|
| WorkOS (Production env) | **Redirects** | Redirect `https://<web>/callback`, sign-in `https://<web>/sign-in`, sign-out `https://<web>/` |
| GitHub App | app **General** settings | Callback `https://<web>/integrations/github/callback`; Webhook **Active**, URL `https://<web>/integrations/github/webhook`, secret = `RELAY_GITHUB_WEBHOOK_SECRET` (`openssl rand -hex 32`) |
| Linear OAuth app | app settings | `https://<web>/integrations/linear/callback` |
| Notion public integration | **Redirect URIs** | `https://<web>/integrations/notion/callback` |
| Resend | **Domains** | verify the sending domain |

---

## 3. Sharing with a teammate

- Never send `.env` files. Production values stay in Render, Vercel and GitHub; add the
  teammate as a collaborator there only if they must manage production.
- Each developer creates their own WorkOS Staging project, GitHub App, Linear app and Notion
  integration for local work (the steps above take about 15 minutes).
- If a single shared development key is unavoidable (for example one AI key), send only that
  value through a password manager or a one-time secret link, then rotate it later.
- After a secret is pasted anywhere public or semi-public, rotate it: generate a new one in the
  same dashboard, update Render/Vercel/GitHub, redeploy, then revoke the old one.
