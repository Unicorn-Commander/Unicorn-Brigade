# 🐳 Docker Deployment Guide - Unicorn Command & Control

## Overview

Complete Docker setup for Unicorn Command & Control with all services containerized and production-ready. Works on Mac Studio for development and Linux servers for production.

## Architecture

```
┌─────────────────────────────────────────────────┐
│                  NGINX (80/443)                 │
│              (Reverse Proxy + SSL)              │
└─────────────┬───────────────────────────────────┘
              │
    ┌─────────┴─────────┬─────────────┬──────────┐
    ▼                   ▼             ▼          ▼
┌──────────┐    ┌──────────────┐  ┌────────┐  ┌─────────┐
│ Frontend │    │   Backend    │  │LiveKit │  │   MCP   │
│  (React) │    │   (Node.js)  │  │(WebRTC)│  │ Server  │
│   :8113  │    │    :8112     │  │ :7880  │  │  :3002  │
└──────────┘    └───────┬──────┘  └────┬───┘  └─────────┘
                        │               │
            ┌───────────┴───────────────┴────────┐
            ▼                                    ▼
      ┌──────────┐                        ┌──────────┐
      │PostgreSQL│                        │  Redis   │
      │   :5432  │                        │  :6379   │
      └──────────┘                        └──────────┘
```

## 🚀 Quick Start

### Development (Mac Studio)

```bash
# 1. Clone and setup
cd ~/unicorn-command-control

# 2. Configure environment
cp .env.docker .env
# Edit .env and add your API keys

# 3. Start all services
./docker-start.sh

# Access at:
# Frontend: http://localhost:8113
# Backend: http://localhost:8112
```

### Production (Linux Server)

```bash
# 1. Install Docker & Docker Compose
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 2. Clone repository
git clone https://github.com/yourusername/unicorn-command-control.git
cd unicorn-command-control

# 3. Configure production environment
cp .env.docker .env
vim .env  # Add production API keys and secrets

# 4. Generate SSL certificates
mkdir ssl
# Add your cert.pem and key.pem files

# 5. Start with production profile
docker-compose --profile production up -d
```

## 📦 Services

### Core Services (Always Running)

| Service | Port | Description |
|---------|------|-------------|
| **PostgreSQL** | 5432 | Primary database |
| **Redis** | 6379 | Cache & pub/sub |
| **Backend** | 8112 | API server |
| **Frontend** | 8113 | Web UI |
| **LiveKit** | 7880 | Voice/video WebRTC |

### Optional Services (Profiles)

| Service | Profile | Port | Description |
|---------|---------|------|-------------|
| **MCP Server** | `mcp` | 3002 | Model Context Protocol |
| **Apache Tika** | `document-processing` | 9998 | Document extraction |
| **SearXNG** | `search` | 8080 | Private web search |
| **Nginx** | `production` | 80/443 | Reverse proxy + SSL |

## 🔧 Configuration

### Environment Variables

```bash
# Database
POSTGRES_PASSWORD=secure_password_here
DATABASE_URL=postgresql://unicorn:REMOVED@postgres:5432/unicorn_db

# Security
JWT_SECRET=your_jwt_secret_min_32_chars
ENCRYPTION_KEY=your_encryption_key_32_chars

# LiveKit (Voice/Video)
LIVEKIT_API_KEY=your_livekit_key
LIVEKIT_API_SECRET=your_livekit_secret

# AI Providers
OPENROUTER_API_KEY=sk-or-v1-000000000000000000000000000000000000
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

## 🛠️ Management Commands

### Start Services

```bash
# Start all core services
./docker-start.sh

# Start with optional services
ENABLE_MCP=true ENABLE_TIKA=true ./docker-start.sh

# Start specific profile
docker-compose --profile mcp up -d
```

### Stop Services

```bash
# Stop all services
./docker-stop.sh

# Stop and remove volumes
docker-compose down -v
```

### View Logs

```bash
# All services
docker-compose logs -f

# Specific service
docker-compose logs -f backend
docker-compose logs -f frontend
```

### Database Management

```bash
# Run migrations
docker-compose exec backend npx prisma migrate deploy

# Access database
docker-compose exec postgres psql -U unicorn -d unicorn_db

# Backup database
docker-compose exec postgres pg_dump -U unicorn unicorn_db > backup.sql

# Restore database
docker-compose exec -T postgres psql -U unicorn unicorn_db < backup.sql
```

### Shell Access

```bash
# Backend shell
docker-compose exec backend sh

# Frontend shell
docker-compose exec frontend sh

# Database shell
docker-compose exec postgres psql -U unicorn
```

## 🔄 Updates & Rebuilds

```bash
# Pull latest code
git pull

# Rebuild containers
docker-compose build --no-cache

# Restart with new build
docker-compose up -d --build
```

## 📊 Monitoring

### Health Checks

```bash
# Check all services
docker-compose ps

# Health endpoints
curl http://localhost:8112/health  # Backend
curl http://localhost:8113/health  # Frontend
```

### Resource Usage

```bash
# Container stats
docker stats

# Disk usage
docker system df

# Clean unused resources
docker system prune -a
```

## 🚢 Production Deployment

### 1. Server Requirements

- **OS**: Ubuntu 22.04 LTS or similar
- **RAM**: 8GB minimum (16GB recommended)
- **CPU**: 4 cores minimum
- **Storage**: 50GB SSD
- **Ports**: 80, 443, 7880-7882

### 2. Security Checklist

- [ ] Change all default passwords
- [ ] Generate new JWT secret
- [ ] Configure SSL certificates
- [ ] Enable firewall (ufw/iptables)
- [ ] Set up fail2ban
- [ ] Configure backup strategy
- [ ] Monitor with Prometheus/Grafana

### 3. Scaling Options

```yaml
# docker-compose.override.yml for scaling
services:
  backend:
    deploy:
      replicas: 3
      resources:
        limits:
          cpus: '2'
          memory: 2G
```

### 4. Backup Strategy

```bash
#!/bin/bash
# backup.sh - Run daily via cron

BACKUP_DIR="/backup/unicorn"
DATE=$(date +%Y%m%d)

# Database backup
docker-compose exec -T postgres pg_dump -U unicorn unicorn_db > $BACKUP_DIR/db_$DATE.sql

# Volume backup
docker run --rm -v uc2-backend-uploads:/data -v $BACKUP_DIR:/backup alpine tar czf /backup/uploads_$DATE.tar.gz -C /data .

# Keep only 30 days
find $BACKUP_DIR -name "*.sql" -mtime +30 -delete
find $BACKUP_DIR -name "*.tar.gz" -mtime +30 -delete
```

## 🐛 Troubleshooting

### Container Won't Start

```bash
# Check logs
docker-compose logs backend

# Common issues:
# - Port already in use: Change ports in docker-compose.yml
# - Permission issues: sudo chown -R 1000:1000 ./volumes
# - Database not ready: Wait or restart
```

### Database Connection Issues

```bash
# Reset database
docker-compose down -v
docker-compose up -d postgres
docker-compose exec backend npx prisma migrate deploy
```

### Frontend White Page

```bash
# Rebuild frontend
docker-compose build --no-cache frontend
docker-compose up -d frontend
```

### Memory Issues

```bash
# Increase Docker memory (Mac)
# Docker Desktop > Preferences > Resources > Memory: 8GB

# Linux: Check docker daemon.json
sudo vim /etc/docker/daemon.json
```

## 🌍 Cloud Deployment Options

### AWS ECS

```bash
# Use ecs-cli or AWS Console
ecs-cli compose up --cluster unicorn-cluster
```

### Google Cloud Run

```bash
gcloud run deploy unicorn-backend --source .
```

### DigitalOcean App Platform

```bash
doctl apps create --spec .do/app.yaml
```

### Kubernetes

```bash
# Convert to K8s manifests
kompose convert -f docker-compose.yml
kubectl apply -f .
```

## 📝 Environment-Specific Configs

### Development

```yaml
# docker-compose.dev.yml
services:
  backend:
    volumes:
      - ./backend:/app
    command: npm run dev
```

### Staging

```yaml
# docker-compose.staging.yml
services:
  backend:
    environment:
      NODE_ENV: staging
      LOG_LEVEL: debug
```

### Production

```yaml
# docker-compose.prod.yml
services:
  backend:
    environment:
      NODE_ENV: production
      LOG_LEVEL: error
    deploy:
      replicas: 3
```

## 🔗 Related Documentation

- [Main README](README.md)
- [API Documentation](docs/API.md)
- [Agent Architecture](docs/AGENT_ARCHITECTURE.md)
- [AP2 Protocol Integration](docs/AP2_INTEGRATION_PLAN.md)

---

**Last Updated**: September 22, 2025
**Version**: 1.0.0
**Status**: Production Ready 🚀