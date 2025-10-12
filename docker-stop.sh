#!/bin/bash

# Unicorn Command & Control - Docker Shutdown Script

echo "🛑 Stopping Unicorn Command & Control..."

# Stop all containers
docker-compose down

echo "✅ All services stopped"
echo ""
echo "To remove volumes (database data): docker-compose down -v"
echo "To restart: ./docker-start.sh"