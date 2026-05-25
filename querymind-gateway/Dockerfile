# ── QueryMind API Gateway Dockerfile (NestJS) ────────────────────────────────
# Build context: ./querymind-gateway
#
# In docker-compose.yml:
#   build:
#     context: ./querymind-gateway
#     dockerfile: Dockerfile

# ── Stage 1: Builder ──────────────────────────────────────────────────────────
FROM node:20-alpine AS builder

WORKDIR /app

# Copy package files first for better layer caching
COPY package*.json ./

# Install ALL dependencies (including devDependencies for build)
RUN npm ci

# Copy source code
COPY . .

# Build the NestJS app
RUN npm run build

# ── Stage 2: Runtime ──────────────────────────────────────────────────────────
FROM node:20-alpine AS runtime

RUN apk add --no-cache curl

# Non-root user for security
RUN addgroup -g 1001 appgroup && \
    adduser -u 1001 -G appgroup -s /bin/sh -D appuser

WORKDIR /app

# Copy package files
COPY package*.json ./

# Install production dependencies only
RUN npm ci --omit=dev && npm cache clean --force

# Copy built output from builder stage
COPY --from=builder /app/dist ./dist

# Fix ownership
RUN chown -R appuser:appgroup /app

USER appuser

EXPOSE 8000

CMD ["node", "dist/main.js"]
