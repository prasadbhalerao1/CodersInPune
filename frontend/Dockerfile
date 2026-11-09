# Relay web (Next.js standalone server). Build args are not secrets: every WorkOS and
# Relay value is read at runtime from the environment (see deploy/.env.production.example).
FROM node:22-slim AS deps
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

FROM node:22-slim AS build
RUN corepack enable
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
# NEXT_PUBLIC_* values are inlined into browser code at build time.
ARG NEXT_PUBLIC_WORKOS_REDIRECT_URI
ENV NEXT_TELEMETRY_DISABLED=1 NEXT_PUBLIC_WORKOS_REDIRECT_URI=$NEXT_PUBLIC_WORKOS_REDIRECT_URI
RUN pnpm build

FROM node:22-slim
WORKDIR /app
ENV NODE_ENV=production NEXT_TELEMETRY_DISABLED=1 PORT=3000 HOSTNAME=0.0.0.0
RUN useradd --system --uid 10001 --no-create-home relay
COPY --from=build --chown=relay /app/.next/standalone ./
COPY --from=build --chown=relay /app/.next/static ./.next/static
COPY --from=build --chown=relay /app/public ./public
USER relay
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=3s --start-period=20s --retries=3   CMD ["node", "-e", "fetch('http://127.0.0.1:3000/').then(r => process.exit(r.status < 500 ? 0 : 1)).catch(() => process.exit(1))"]
CMD ["node", "server.js"]
