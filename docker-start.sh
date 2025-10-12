#!/bin/bash

# Unicorn Command & Control - Docker Startup Script

set -e

echo "🦄 Starting Unicorn Command & Control..."

# Load environment variables
if [ -f .env.docker ]; then
    export $(cat .env.docker | grep -v '^#' | xargs)
    echo "✅ Environment variables loaded"
else
    echo "⚠️  Warning: .env.docker not found, using defaults"
fi

# Check Docker
if ! docker info > /dev/null 2>&1; then
    echo "❌ Docker is not running. Please start Docker Desktop."
    exit 1
fi

echo "📦 Building containers..."

# Build and start core services
docker-compose up -d postgres redis

echo "⏳ Waiting for database..."
sleep 5

# Run database migrations
echo "🔄 Running database migrations..."
docker-compose run --rm backend npx prisma migrate deploy

# Start all services
echo "🚀 Starting all services..."
docker-compose up -d backend frontend livekit

# Optional services based on environment
if [ "$ENABLE_MCP" = "true" ]; then
    echo "🔌 Starting MCP server..."
    docker-compose --profile mcp up -d
fi

if [ "$ENABLE_TIKA" = "true" ]; then
    echo "📄 Starting Apache Tika..."
    docker-compose --profile document-processing up -d
fi

if [ "$ENABLE_SEARXNG" = "true" ]; then
    echo "🔍 Starting SearXNG..."
    docker-compose --profile search up -d
fi

echo ""
echo "✨ Unicorn Command & Control is running!"
echo ""
echo "🌐 Frontend: http://localhost:8113"
echo "🔧 Backend API: http://localhost:8112"
echo "🎙️ LiveKit: http://localhost:7880"
echo "🗄️ PostgreSQL: localhost:5432"
echo "💾 Redis: localhost:6379"
echo ""
echo "📊 View logs: docker-compose logs -f"
echo "🛑 Stop all: ./docker-stop.sh"
echo ""

# Show container status
docker-compose ps