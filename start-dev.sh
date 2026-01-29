#!/bin/bash
# Unicorn Brigade — Development Launcher
# Starts backend API + frontend dev server

set -e

PROJECT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$PROJECT_DIR"

# Colors
GREEN='\033[0;32m'
PURPLE='\033[0;35m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${PURPLE}"
echo "  🦄 Unicorn Brigade — Agent Infrastructure Platform"
echo "  ═══════════════════════════════════════════════════"
echo -e "${NC}"

# Check prerequisites
echo -e "${CYAN}Checking prerequisites...${NC}"

# Check PostgreSQL (database)
if command -v pg_isready > /dev/null 2>&1; then
    if pg_isready -h localhost -p 5434 > /dev/null 2>&1; then
        echo -e "  ✓ PostgreSQL running on :5434"
    else
        echo -e "  ${YELLOW}⚠ PostgreSQL not reachable on :5434${NC}"
        echo -e "  ${YELLOW}  Attempting to start magic-unicorn-postgres...${NC}"
        docker start magic-unicorn-postgres 2>/dev/null || \
            echo -e "  ${YELLOW}⚠ Could not start PostgreSQL. Database features will be limited.${NC}"
        # Wait for it to be ready
        for i in $(seq 1 10); do
            if pg_isready -h localhost -p 5434 > /dev/null 2>&1; then
                echo -e "  ✓ PostgreSQL is now ready"
                break
            fi
            sleep 1
        done
    fi
else
    # Fallback: check via Docker if pg_isready is not installed locally
    if docker exec magic-unicorn-postgres pg_isready -U leads_user > /dev/null 2>&1; then
        echo -e "  ✓ PostgreSQL running on :5434 (checked via Docker)"
    else
        echo -e "  ${YELLOW}⚠ PostgreSQL not reachable. Starting magic-unicorn-postgres...${NC}"
        docker start magic-unicorn-postgres 2>/dev/null || \
            echo -e "  ${YELLOW}⚠ Could not start PostgreSQL. Database features will be limited.${NC}"
    fi
fi

# Check Qdrant (vector memory)
if curl -s http://localhost:6333/collections > /dev/null 2>&1; then
    echo -e "  ✓ Qdrant vector DB running on :6333"
else
    echo -e "  ${YELLOW}⚠ Qdrant not running. Starting via Docker...${NC}"
    docker run -d --name qdrant -p 6333:6333 -p 6334:6334 qdrant/qdrant:latest 2>/dev/null || \
    docker start qdrant 2>/dev/null || \
    echo -e "  ${YELLOW}⚠ Could not start Qdrant. Memory features will be limited.${NC}"
fi

# Activate Python venv
if [ -d "$PROJECT_DIR/venv" ]; then
    source "$PROJECT_DIR/venv/bin/activate"
    echo -e "  ✓ Python venv activated"
else
    echo -e "  ${YELLOW}⚠ No venv found. Run: python3 -m venv venv && pip install -r requirements.txt${NC}"
    exit 1
fi

# Run database initialization / migrations
echo ""
echo -e "${CYAN}Running database initialization...${NC}"
cd "$PROJECT_DIR"
python -m app.db.init_db 2>/dev/null && \
    echo -e "  ✓ Database initialized" || \
    echo -e "  ${YELLOW}⚠ Database init skipped (module may not exist yet)${NC}"

# Start backend
echo ""
echo -e "${CYAN}Starting backend API server...${NC}"
cd "$PROJECT_DIR"
python -m uvicorn app.main:app --host 0.0.0.0 --port 8100 --reload &
BACKEND_PID=$!
echo -e "  ✓ Backend starting on ${GREEN}http://localhost:8100${NC} (PID: $BACKEND_PID)"

# Wait for backend to be ready
echo -n "  Waiting for backend..."
for i in $(seq 1 15); do
    if curl -s http://localhost:8100/api/v1/health > /dev/null 2>&1; then
        echo -e " ${GREEN}ready!${NC}"
        break
    fi
    echo -n "."
    sleep 1
done

# Start frontend
echo ""
echo -e "${CYAN}Starting frontend dev server...${NC}"
cd "$PROJECT_DIR/frontend"
npm run dev &
FRONTEND_PID=$!
echo -e "  ✓ Frontend starting on ${GREEN}http://localhost:5173${NC} (PID: $FRONTEND_PID)"

# Summary
sleep 2
echo ""
echo -e "${PURPLE}═══════════════════════════════════════════════════${NC}"
echo -e "${GREEN}  Platform is running!${NC}"
echo ""
echo -e "  🌐 Frontend:  ${GREEN}http://localhost:5173${NC}"
echo -e "  🔌 Backend:   ${GREEN}http://localhost:8100${NC}"
echo -e "  📡 API Docs:  ${GREEN}http://localhost:8100/docs${NC}"
echo -e "  🧠 Qdrant:    ${GREEN}http://localhost:6333/dashboard${NC}"
echo ""
echo -e "  ${CYAN}Keyboard shortcuts:${NC}"
echo -e "    Cmd+K    Command palette"
echo -e "    Ctrl+C   Stop all services"
echo -e "${PURPLE}═══════════════════════════════════════════════════${NC}"

# Trap to clean up both processes
cleanup() {
    echo ""
    echo -e "${YELLOW}Shutting down...${NC}"
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    wait $BACKEND_PID 2>/dev/null
    wait $FRONTEND_PID 2>/dev/null
    echo -e "${GREEN}Done.${NC}"
}

trap cleanup EXIT INT TERM

# Wait for either process to exit
wait
