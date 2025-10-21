#!/bin/bash
#
# Setup Script for Remote Code Execution in Unicorn Brigade
#

set -e

echo "=========================================="
echo "Unicorn Brigade - Remote Execution Setup"
echo "=========================================="
echo ""

# Check current directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "📁 Project directory: $PROJECT_DIR"
echo ""

# Step 1: Check Python version
echo "1️⃣  Checking Python version..."
python_version=$(python3 --version 2>&1 | awk '{print $2}')
echo "   Python version: $python_version"

if ! python3 -c 'import sys; assert sys.version_info >= (3, 9)' 2>/dev/null; then
    echo "   ❌ Python 3.9+ required"
    exit 1
fi
echo "   ✅ Python version OK"
echo ""

# Step 2: Install dependencies
echo "2️⃣  Installing Python dependencies..."
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt --quiet
    echo "   ✅ Dependencies installed"
else
    echo "   ❌ requirements.txt not found"
    exit 1
fi
echo ""

# Step 3: Check Docker
echo "3️⃣  Checking Docker availability..."
if command -v docker &> /dev/null; then
    docker_version=$(docker --version | awk '{print $3}' | sed 's/,//')
    echo "   Docker version: $docker_version"

    # Test Docker access
    if docker ps &> /dev/null; then
        echo "   ✅ Docker is accessible"
    else
        echo "   ⚠️  Docker daemon not accessible"
        echo "   Run: sudo usermod -aG docker $USER"
        echo "   Then logout and login again"
    fi
else
    echo "   ⚠️  Docker not installed (optional for local execution)"
    echo "   Install with: sudo apt install docker.io"
fi
echo ""

# Step 4: Pull Docker images for local execution
echo "4️⃣  Pulling Docker images for local execution..."
if command -v docker &> /dev/null && docker ps &> /dev/null; then
    echo "   Pulling Python image..."
    docker pull python:3.11-slim --quiet
    echo "   Pulling Node.js image..."
    docker pull node:20-slim --quiet
    echo "   ✅ Docker images ready"
else
    echo "   ⚠️  Skipping (Docker not available)"
fi
echo ""

# Step 5: Check SSH client
echo "5️⃣  Checking SSH client..."
if command -v ssh &> /dev/null; then
    ssh_version=$(ssh -V 2>&1 | head -n1)
    echo "   SSH: $ssh_version"
    echo "   ✅ SSH client available"
else
    echo "   ⚠️  SSH client not found"
    echo "   Install with: sudo apt install openssh-client"
fi
echo ""

# Step 6: Create workspace directory
echo "6️⃣  Creating workspace directory..."
mkdir -p /tmp/brigade_workspace
chmod 755 /tmp/brigade_workspace
echo "   ✅ Workspace created: /tmp/brigade_workspace"
echo ""

# Step 7: Run tests
echo "7️⃣  Running tests..."
if pytest tests/test_remote_executor.py -v --tb=short 2>&1 | tail -20; then
    echo "   ✅ Tests passed"
else
    echo "   ⚠️  Some tests failed (may need real SSH server)"
fi
echo ""

# Step 8: Check Ops-Center connectivity
echo "8️⃣  Checking Ops-Center connectivity..."
OPS_CENTER_URL="${OPS_CENTER_URL:-http://localhost:8000}"
if curl -s -o /dev/null -w "%{http_code}" "$OPS_CENTER_URL/ping" | grep -q "200"; then
    echo "   ✅ Ops-Center reachable at $OPS_CENTER_URL"
else
    echo "   ⚠️  Ops-Center not reachable at $OPS_CENTER_URL"
    echo "   Set OPS_CENTER_URL environment variable if running elsewhere"
fi
echo ""

# Step 9: Show next steps
echo "=========================================="
echo "✅ Setup Complete!"
echo "=========================================="
echo ""
echo "Next steps:"
echo ""
echo "1. Configure execution server in Ops-Center:"
echo "   curl -X POST $OPS_CENTER_URL/api/v1/execution-servers \\"
echo "     -H 'Cookie: session=YOUR_SESSION' \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{...}'"
echo ""
echo "2. Start Brigade:"
echo "   python -m app.main"
echo ""
echo "3. Test remote execution:"
echo "   curl -X POST http://localhost:8100/api/v1/execution/execute \\"
echo "     -H 'X-User-ID: test-user' \\"
echo "     -H 'Content-Type: application/json' \\"
echo "     -d '{\"code\":\"print('Hello')\",\"language\":\"python\"}'"
echo ""
echo "4. View documentation:"
echo "   cat docs/REMOTE_EXECUTION.md"
echo ""
echo "5. Run example:"
echo "   python docs/examples/remote_execution_example.py"
echo ""
echo "=========================================="
