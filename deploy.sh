#!/bin/bash
# Unicorn Brigade — Production Deployment Script
# Works on both Mac Studio (local) and VPS
#
# Usage:
#   ./deploy.sh          # Build and start all services
#   ./deploy.sh --build  # Force rebuild all containers
#   ./deploy.sh --down   # Stop all services

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

# Colors
GREEN='\033[0;32m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

echo -e "${PURPLE}"
echo "  Deploying Unicorn Brigade..."
echo "  ============================================="
echo -e "${NC}"

# ── Handle --down flag ──────────────────────────────────────────────────────
if [ "$1" = "--down" ]; then
    echo -e "${YELLOW}Stopping all services...${NC}"
    docker compose down
    echo -e "${GREEN}All services stopped.${NC}"
    exit 0
fi

# ── Check prerequisites ────────────────────────────────────────────────────
echo -e "${CYAN}Checking prerequisites...${NC}"

command -v docker >/dev/null 2>&1 || { echo -e "${RED}Docker required but not installed.${NC}"; exit 1; }

# Support both docker-compose (v1) and docker compose (v2)
if command -v docker compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    echo -e "${RED}Docker Compose required but not installed.${NC}"
    exit 1
fi

echo -e "  OK Docker and Docker Compose available"

# ── Check .env exists ──────────────────────────────────────────────────────
if [ ! -f .env ]; then
    echo -e "${RED}No .env file found.${NC}"
    echo ""
    echo "  Copy the production template and configure it:"
    echo ""
    echo "    cp .env.production .env"
    echo "    # Edit .env with your actual passwords and keys"
    echo ""
    exit 1
fi

echo -e "  OK .env file found"

# ── Warn about placeholder passwords ──────────────────────────────────────
if grep -q "CHANGE_ME" .env 2>/dev/null; then
    echo -e "${YELLOW}  WARNING: .env still contains CHANGE_ME placeholders!${NC}"
    echo -e "${YELLOW}  Update all passwords before deploying to production.${NC}"
    echo ""
    read -p "  Continue anyway? (y/N) " -n 1 -r
    echo ""
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# ── Build containers ──────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}Building containers...${NC}"
$COMPOSE_CMD build

# ── Start services ────────────────────────────────────────────────────────
echo ""
echo -e "${CYAN}Starting services...${NC}"
$COMPOSE_CMD up -d

# ── Wait for PostgreSQL ──────────────────────────────────────────────────
echo ""
echo -n -e "${CYAN}Waiting for PostgreSQL...${NC}"
RETRIES=0
MAX_RETRIES=30
until $COMPOSE_CMD exec brigade-postgres pg_isready -U ${POSTGRES_USER:-brigade} > /dev/null 2>&1; do
    RETRIES=$((RETRIES + 1))
    if [ $RETRIES -ge $MAX_RETRIES ]; then
        echo ""
        echo -e "${RED}PostgreSQL did not become ready in time.${NC}"
        echo "  Check logs: $COMPOSE_CMD logs brigade-postgres"
        exit 1
    fi
    echo -n "."
    sleep 2
done
echo -e " ${GREEN}ready!${NC}"

# ── Wait for API to be healthy ──────────────────────────────────────────
echo -n -e "${CYAN}Waiting for API...${NC}"
RETRIES=0
MAX_RETRIES=30
until curl -sf http://localhost:8100/api/v1/health > /dev/null 2>&1; do
    RETRIES=$((RETRIES + 1))
    if [ $RETRIES -ge $MAX_RETRIES ]; then
        echo ""
        echo -e "${YELLOW}API health check timed out (may still be starting).${NC}"
        echo "  Check logs: $COMPOSE_CMD logs brigade-api"
        break
    fi
    echo -n "."
    sleep 2
done
echo -e " ${GREEN}ready!${NC}"

# ── Run database initialization ─────────────────────────────────────────
echo ""
echo -e "${CYAN}Running database initialization...${NC}"
$COMPOSE_CMD exec brigade-api python -m app.db.init_db 2>/dev/null || \
    echo -e "${YELLOW}  Database init skipped (module may not exist yet).${NC}"

# ── Summary ─────────────────────────────────────────────────────────────
echo ""
echo -e "${PURPLE}=============================================${NC}"
echo -e "${GREEN}  Unicorn Brigade is running!${NC}"
echo ""
echo -e "  Frontend: ${GREEN}http://localhost:3000${NC}"
echo -e "  Backend:  ${GREEN}http://localhost:8100${NC}"
echo -e "  API Docs: ${GREEN}http://localhost:8100/docs${NC}"
echo ""
echo -e "  ${CYAN}Useful commands:${NC}"
echo -e "    Logs:    $COMPOSE_CMD logs -f"
echo -e "    Stop:    $COMPOSE_CMD down"
echo -e "    Restart: $COMPOSE_CMD restart"
echo -e "    Status:  $COMPOSE_CMD ps"
echo -e "${PURPLE}=============================================${NC}"
