# =============================================================================
# SMC Dashboard - Dockerfile (Multi-stage Build)
# =============================================================================
# Stage 1: Build
# =============================================================================
FROM node:22-alpine AS builder

WORKDIR /app

# Instalar pnpm
RUN corepack enable && corepack prepare pnpm@latest --activate

# Copiar manifests primeiro para cache de dependências
COPY package.json ./
COPY pnpm-lock.yaml* ./

# Instalar dependências
RUN pnpm install --frozen-lockfile 2>/dev/null || pnpm install

# Copiar código fonte
COPY client/ ./client/
COPY server/ ./server/
COPY shared/ ./shared/
COPY tsconfig.json ./
COPY vite.config.ts ./
COPY components.json ./

# Build de produção
RUN pnpm build

# =============================================================================
# Stage 2: Production
# =============================================================================
FROM node:22-alpine AS production

LABEL maintainer="SMC Trading"
LABEL version="1.0.0"
LABEL description="SMC Order Block Dashboard"

WORKDIR /app

# Copiar artefatos de build
COPY --from=builder /app/dist ./dist

# Instalar apenas express para servir
RUN npm install express@4

# Expor porta
EXPOSE 3000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD wget -qO- http://localhost:3000/ || exit 1

# Comando de inicialização
CMD ["node", "dist/index.js"]
