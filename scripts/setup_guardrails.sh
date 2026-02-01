#!/bin/bash
# Guardrails Setup Script for Unicorn Brigade
# This script sets up the guardrails infrastructure

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

echo "============================================"
echo "Unicorn Brigade - Guardrails Setup"
echo "============================================"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Helper functions
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Check prerequisites
check_prerequisites() {
    info "Checking prerequisites..."

    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed. Please install Docker first."
    fi
    info "Docker: $(docker --version)"

    # Check Docker Compose
    if ! command -v docker compose &> /dev/null; then
        if ! command -v docker-compose &> /dev/null; then
            error "Docker Compose is not installed. Please install Docker Compose first."
        fi
    fi
    info "Docker Compose: Available"

    # Check if brigade-network exists
    if ! docker network inspect brigade-network &> /dev/null; then
        warn "brigade-network does not exist. Creating it..."
        docker network create brigade-network
        info "Created brigade-network"
    else
        info "brigade-network: Exists"
    fi

    echo ""
}

# Build services
build_services() {
    info "Building guardrails services..."

    cd "$PROJECT_DIR"

    # Build Llama Guard service
    if [ -d "services/llama-guard" ]; then
        info "Building Llama Guard service..."
        docker build -t brigade-llama-guard-service:latest services/llama-guard/
    fi

    # Build Guardrails AI service
    if [ -d "services/guardrails-ai" ]; then
        info "Building Guardrails AI service..."
        docker build -t brigade-guardrails-ai:latest services/guardrails-ai/
    fi

    echo ""
}

# Start services
start_services() {
    info "Starting guardrails services..."

    cd "$PROJECT_DIR"

    # Start with docker compose
    docker compose -f docker-compose.yml -f docker-compose.guardrails.yml up -d

    echo ""
    info "Waiting for services to be healthy..."
    sleep 10

    # Check service health
    check_service_health "presidio-analyzer" "http://localhost:5001/health"
    check_service_health "presidio-anonymizer" "http://localhost:5002/health"
    check_service_health "llama-guard-service" "http://localhost:8085/health"
    check_service_health "guardrails-ai" "http://localhost:8086/health"

    echo ""
}

# Check service health
check_service_health() {
    local service_name=$1
    local health_url=$2

    echo -n "Checking $service_name... "

    for i in {1..30}; do
        if curl -s -f "$health_url" > /dev/null 2>&1; then
            echo -e "${GREEN}Healthy${NC}"
            return 0
        fi
        sleep 2
    done

    echo -e "${YELLOW}Not ready (may still be starting)${NC}"
    return 1
}

# Pull Llama Guard model
pull_llama_guard_model() {
    info "Pulling Llama Guard model (this may take a few minutes)..."

    docker exec brigade-llama-guard ollama pull llama-guard3:1b || {
        warn "Could not pull model automatically. It will be pulled on first request."
    }

    echo ""
}

# Test guardrails
test_guardrails() {
    info "Testing guardrails..."

    echo ""
    echo "1. Testing Presidio Analyzer..."
    curl -s -X POST http://localhost:5001/analyze \
        -H "Content-Type: application/json" \
        -d '{"text": "My email is test@example.com and my SSN is 123-45-6789", "language": "en"}' \
        | python3 -m json.tool 2>/dev/null || echo "Presidio analyzer test completed"

    echo ""
    echo "2. Testing Llama Guard Service..."
    curl -s -X POST http://localhost:8085/check \
        -H "Content-Type: application/json" \
        -d '{"text": "Hello, how are you today?", "check_type": "input"}' \
        | python3 -m json.tool 2>/dev/null || echo "Llama Guard test completed"

    echo ""
    echo "3. Testing Guardrails AI Service..."
    curl -s http://localhost:8086/guards \
        | python3 -m json.tool 2>/dev/null || echo "Guardrails AI test completed"

    echo ""
}

# Print summary
print_summary() {
    echo ""
    echo "============================================"
    echo "Guardrails Setup Complete!"
    echo "============================================"
    echo ""
    echo "Services running:"
    echo "  - Presidio Analyzer:    http://localhost:5001"
    echo "  - Presidio Anonymizer:  http://localhost:5002"
    echo "  - Llama Guard Service:  http://localhost:8085"
    echo "  - Guardrails AI:        http://localhost:8086"
    echo "  - Guardrails Cache:     localhost:6380"
    echo ""
    echo "Next steps:"
    echo "  1. Copy config/guardrails/litellm_config.yaml to your Ops-Center"
    echo "  2. Update the LiteLLM proxy configuration to include guardrails"
    echo "  3. Set required environment variables"
    echo "  4. Restart the LiteLLM proxy"
    echo ""
    echo "Documentation:"
    echo "  - docs/guardrails-plan.md"
    echo ""
}

# Main execution
main() {
    check_prerequisites

    case "${1:-}" in
        build)
            build_services
            ;;
        start)
            start_services
            ;;
        pull-model)
            pull_llama_guard_model
            ;;
        test)
            test_guardrails
            ;;
        all|"")
            build_services
            start_services
            pull_llama_guard_model
            test_guardrails
            print_summary
            ;;
        stop)
            info "Stopping guardrails services..."
            cd "$PROJECT_DIR"
            docker compose -f docker-compose.yml -f docker-compose.guardrails.yml down
            info "Services stopped."
            ;;
        *)
            echo "Usage: $0 [command]"
            echo ""
            echo "Commands:"
            echo "  all         Build, start, and test all services (default)"
            echo "  build       Build Docker images only"
            echo "  start       Start services only"
            echo "  pull-model  Pull Llama Guard model"
            echo "  test        Test guardrail endpoints"
            echo "  stop        Stop all guardrail services"
            exit 1
            ;;
    esac
}

main "$@"
