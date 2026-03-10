FROM node:22-alpine AS builder

WORKDIR /app

# Install dependencies first (layer cached unless package.json changes)
COPY package.json package-lock.json* ./
RUN npm ci --legacy-peer-deps

# Copy source (excludes .env.local via .dockerignore)
COPY . .

# Build-time env defaults — can be overridden with --build-arg
ARG EXPO_PUBLIC_PRODUCTION_API_URL=http://13.234.238.175:8081/api/v1
ARG EXPO_PUBLIC_USE_PRODUCTION_API=true

ENV EXPO_PUBLIC_PRODUCTION_API_URL=$EXPO_PUBLIC_PRODUCTION_API_URL
ENV EXPO_PUBLIC_USE_PRODUCTION_API=$EXPO_PUBLIC_USE_PRODUCTION_API
ENV EXPO_NO_DOTENV=1

# Export static web build — no Metro bundler at runtime
RUN npx expo export --platform web

# ── Runtime stage ────────────────────────────────────────────────
FROM node:22-alpine

WORKDIR /app

RUN npm install -g serve@14

COPY --from=builder /app/dist ./dist

EXPOSE 8081

CMD ["serve", "-p", "8081", "-s", "dist"]
