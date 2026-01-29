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

# Build the production bundle
RUN npm run build

# ── Serve Stage ──────────────────────────────────────────────────────────────
FROM nginx:alpine AS production

# Remove default nginx static content
RUN rm -rf /usr/share/nginx/html/*

# Copy the built assets from the build stage
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

# Expose HTTP port
EXPOSE 80

# nginx runs in the foreground by default with the alpine image
CMD ["nginx", "-g", "daemon off;"]
