# Unicorn Brigade Frontend — Multi-stage Docker Build
# Stage 1: Build the React/Vite application
# Stage 2: Serve with nginx

# ── Build Stage ──────────────────────────────────────────────────────────────
FROM node:20-alpine AS build

WORKDIR /app

# Copy package files first for better Docker layer caching
COPY package.json package-lock.json* ./

# Install dependencies (clean install for reproducible builds)
RUN npm ci

# Copy the rest of the frontend source
COPY . .

# Accept Vite env vars as build args (baked at build time)
ARG VITE_API_URL=/api/v1
ARG VITE_WS_URL=ws://localhost:8100
ARG VITE_OPS_CENTER_URL=http://localhost:8084
ARG VITE_DEV_MODE=false
ENV VITE_API_URL=$VITE_API_URL
ENV VITE_WS_URL=$VITE_WS_URL
ENV VITE_OPS_CENTER_URL=$VITE_OPS_CENTER_URL
ENV VITE_DEV_MODE=$VITE_DEV_MODE

# Build the production bundle
RUN npm run build

# ── Serve Stage ──────────────────────────────────────────────────────────────
FROM nginx:alpine AS production

# Remove default nginx static content
RUN rm -rf /usr/share/nginx/html/*

# Copy the built assets from the build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy nginx config as a template (envsubst replaces ${BRIGADE_API_KEY} at startup)
COPY nginx.conf.template /etc/nginx/templates/default.conf.template

# Expose HTTP port
EXPOSE 80

# nginx Docker image auto-runs envsubst on /etc/nginx/templates/*.template
# and outputs to /etc/nginx/conf.d/ before starting nginx
CMD ["nginx", "-g", "daemon off;"]
