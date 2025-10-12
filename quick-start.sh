#!/bin/bash

# Unicorn Battalion Quick Start Script - New Architecture
# This script automates the setup process for the new Unicorn Battalion architecture

set -e  # Exit on error

echo "=================================="
echo "🦄 Unicorn Battalion Quick Start - New Architecture"
echo "=================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if .env exists
if [ ! -f .env ]; then
    echo "${YELLOW}📝 No .env file found. Creating from template...${NC}"
    cp .env.new-architecture .env
    echo "${GREEN}✓ Created .env from template${NC}"
    echo ""
    echo "${RED}⚠️  IMPORTANT: Edit .env and add your API keys!${NC}"
    echo "   Minimum required: OPENROUTER_API_KEY"
    echo ""
    read -p "Press Enter after you've added your OPENROUTER_API_KEY to .env..."
fi

# Verify OpenRouter key is set
if ! grep -q "^OPENROUTER_API_KEY=.\+" .env; then
    echo "${RED}❌ OPENROUTER_API_KEY not set in .env${NC}"
    echo "   Please edit .env and add your OpenRouter API key"
    exit 1
fi

echo "${GREEN}✓ API key configured${NC}"
echo ""

# Install dependencies
echo "${YELLOW}📦 Installing dependencies...${NC}"
npm install

if [ $? -eq 0 ]; then
    echo "${GREEN}✓ Dependencies installed${NC}"
else
    echo "${RED}❌ Failed to install dependencies${NC}"
    exit 1
fi
echo ""

# Check if Docker is running
echo "${YELLOW}🐳 Checking Docker...${NC}"
if ! docker info > /dev/null 2>&1; then
    echo "${RED}❌ Docker is not running${NC}"
    echo "   Please start Docker and run this script again"
    exit 1
fi
echo "${GREEN}✓ Docker is running${NC}"
echo ""

# Start infrastructure
echo "${YELLOW}🚀 Starting infrastructure services...${NC}"
echo ""

echo "Select infrastructure setup:"
echo "1) Minimal (Qdrant only - recommended for getting started)"
echo "2) Standard (Qdrant + PostgreSQL)"
echo "3) Full (Qdrant + PostgreSQL + Neo4j for graph memory)"
echo "4) Complete (Everything + LiteLLM proxy)"
echo ""
read -p "Choose option [1-4]: " infra_choice

case $infra_choice in
    1)
        echo "Starting Qdrant..."
        docker compose -f docker-compose.new-architecture.yml up qdrant -d
        ;;
    2)
        echo "Starting Qdrant and PostgreSQL..."
        docker compose -f docker-compose.new-architecture.yml up qdrant postgres -d
        ;;
    3)
        echo "Starting Qdrant, PostgreSQL, and Neo4j..."
        docker compose -f docker-compose.new-architecture.yml --profile graph-memory up qdrant postgres neo4j -d
        ;;
    4)
        echo "Starting full stack..."
        docker compose -f docker-compose.new-architecture.yml --profile graph-memory --profile litellm up -d
        ;;
    *)
        echo "Invalid choice. Starting minimal setup..."
        docker compose -f docker-compose.new-architecture.yml up qdrant -d
        ;;
esac

echo ""
echo "${YELLOW}⏳ Waiting for services to be ready...${NC}"
sleep 5

# Check Qdrant
echo -n "Checking Qdrant... "
if curl -s http://localhost:6333/health > /dev/null; then
    echo "${GREEN}✓${NC}"
else
    echo "${RED}✗ Qdrant not responding${NC}"
    echo "Try: docker logs battalion-qdrant"
fi

# Check Postgres if running
if docker ps | grep -q battalion-postgres; then
    echo -n "Checking PostgreSQL... "
    if docker exec battalion-postgres pg_isready -U battalion > /dev/null 2>&1; then
        echo "${GREEN}✓${NC}"
    else
        echo "${RED}✗ PostgreSQL not ready${NC}"
    fi
fi

# Check Neo4j if running
if docker ps | grep -q battalion-neo4j; then
    echo -n "Checking Neo4j... "
    sleep 10  # Neo4j takes longer to start
    if curl -s http://localhost:7474 > /dev/null; then
        echo "${GREEN}✓${NC}"
    else
        echo "${YELLOW}⏳ Neo4j still starting (this is normal)${NC}"
    fi
fi

# Check LiteLLM if running
if docker ps | grep -q battalion-litellm; then
    echo -n "Checking LiteLLM... "
    if curl -s http://localhost:4000/health > /dev/null; then
        echo "${GREEN}✓${NC}"
    else
        echo "${RED}✗ LiteLLM not responding${NC}"
    fi
fi

echo ""

# Run database migrations if Postgres is running
if docker ps | grep -q battalion-postgres; then
    echo "${YELLOW}🗄️  Running database migrations...${NC}"
    npx prisma migrate deploy
    echo "${GREEN}✓ Migrations complete${NC}"
    echo ""
fi

# Start Unicorn Battalion
echo "${YELLOW}🦄 Starting Unicorn Battalion...${NC}"
echo ""
echo "${GREEN}=================================="
echo "Unicorn Battalion is starting!"
echo "==================================${NC}"
echo ""
echo "📍 Access points:"
echo "   Main: http://localhost:8112"
echo "   Health: http://localhost:8112/api/chat/health"
echo ""
echo "🔧 Services:"
echo "   Qdrant: http://localhost:6333"
if docker ps | grep -q battalion-postgres; then
    echo "   PostgreSQL: localhost:5432"
fi
if docker ps | grep -q battalion-neo4j; then
    echo "   Neo4j: http://localhost:7474"
fi
if docker ps | grep -q battalion-litellm; then
    echo "   LiteLLM: http://localhost:4000"
fi
echo ""
echo "📚 Documentation:"
echo "   Migration Guide: ./MIGRATION_GUIDE.md"
echo "   Example API: ./api/routes/chat-new.js"
echo ""
echo "${YELLOW}Starting server with: npm start${NC}"
echo ""

npm start
