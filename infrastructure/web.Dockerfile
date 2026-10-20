FROM node:24-bookworm-slim AS build
WORKDIR /app
RUN npm install --global pnpm@11.21.0
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml ./
COPY apps/web/package.json ./apps/web/package.json
RUN pnpm install --frozen-lockfile
COPY apps/web ./apps/web
ARG INTERNAL_API_URL=http://api:8000
ENV INTERNAL_API_URL=$INTERNAL_API_URL NEXT_TELEMETRY_DISABLED=1
RUN pnpm build

FROM node:24-bookworm-slim AS runtime
WORKDIR /app
ENV NODE_ENV=production HOSTNAME=0.0.0.0 PORT=3000 INTERNAL_API_URL=http://api:8000
COPY --from=build --chown=node:node /app/apps/web/.next/standalone ./
COPY --from=build --chown=node:node /app/apps/web/.next/static ./apps/web/.next/static
USER node
EXPOSE 3000
CMD ["node", "apps/web/server.js"]
