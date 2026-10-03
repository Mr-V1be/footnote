# syntax=docker/dockerfile:1.7
# The web app as a Next.js standalone server. Build from the repository root:
#   docker build -f frontend/Dockerfile -t snoska-web .

FROM node:24-alpine AS deps
WORKDIR /app/frontend
RUN corepack enable
COPY frontend/package.json frontend/pnpm-lock.yaml frontend/pnpm-workspace.yaml ./
RUN --mount=type=cache,target=/root/.local/share/pnpm/store pnpm install --frozen-lockfile

FROM deps AS build
COPY frontend/ ./
ENV NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

FROM node:24-alpine AS runtime
RUN addgroup -S -g 10001 snoska && adduser -S -u 10001 -G snoska -h /app snoska
WORKDIR /app
COPY --from=build --chown=snoska:snoska /app/frontend/.next/standalone ./
COPY --from=build --chown=snoska:snoska /app/frontend/.next/static ./.next/static
COPY --from=build --chown=snoska:snoska /app/frontend/public ./public
# Demo stand only: the seed names the account each role opens.
COPY backend/demo/seed.yaml /app/demo/seed.yaml
ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1 \
    PORT=3000 \
    HOSTNAME=0.0.0.0 \
    SNOSKA_DEMO_SEED=/app/demo/seed.yaml
USER snoska
EXPOSE 3000
HEALTHCHECK --interval=15s --timeout=5s --start-period=20s --retries=5 \
    CMD ["wget", "-q", "-O", "/dev/null", "http://127.0.0.1:3000/health"]
CMD ["node", "server.js"]
