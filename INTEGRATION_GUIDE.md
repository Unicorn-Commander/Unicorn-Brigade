# Remote Code Execution - Integration Guide

## Quick Start

### 1. Run Setup Script

```bash
cd /home/muut/Production/UC-Cloud/Unicorn-Brigade
./scripts/setup_remote_execution.sh
```

This will:
- ✅ Check Python version
- ✅ Install dependencies (asyncssh, docker, paramiko)
- ✅ Check Docker availability
- ✅ Pull Docker images
- ✅ Create workspace directory
- ✅ Run tests
- ✅ Verify Ops-Center connectivity

### 2. Configure Execution Server (User Side)

Users configure their execution server through Ops-Center:

**Option A: SSH Server**
```bash
curl -X POST https://unicorncommander.ai/api/v1/execution-servers \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Dev Server",
    "server_type": "ssh",
    "connection_config": {
      "host": "dev.example.com",
      "port": 22,
      "username": "developer",
      "auth_method": "key",
      "private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\n...\n-----END OPENSSH PRIVATE KEY-----"
    },
    "workspace_path": "/home/developer/workspace",
    "is_default": true
  }'
```

**Option B: Docker (Local)**
```bash
curl -X POST https://unicorncommander.ai/api/v1/execution-servers \
  -H "Cookie: session=YOUR_SESSION_COOKIE" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Local Docker",
    "server_type": "docker",
    "connection_config": {
      "image": "python:3.11-slim",
      "memoryLimit": "512m"
    },
    "is_default": true
  }'
```

**Option C: No Configuration (Local Fallback)**
If no server is configured, Brigade will execute code locally in sandboxed Docker containers.

### 3. Use in Brigade Agents

```python
from app.agents.code import CodeAgent

# Initialize agent
agent = CodeAgent()

# Execute code on user's server
result = await agent.execute_code(
    code="print('Hello from remote server!')",
    language="python",
    user_id="user-123"
)

print(f"Success: {result['success']}")
print(f"Output: {result['output']}")
print(f"Execution type: {result['execution_type']}")  # ssh, docker, or local
```

## API Endpoints

### Brigade API

All endpoints require `X-User-ID` header.

#### Execute Code
```
POST /api/v1/execution/execute
```

**Request:**
```json
{
  "code": "print('Hello World')",
  "language": "python",
  "timeout": 30,
  "workspace": "/optional/workspace/path"
}
```

**Response:**
```json
{
  "success": true,
  "execution_id": "abc123",
  "language": "python",
  "output": "Hello World\n",
  "error": "",
  "exit_code": 0,
  "execution_type": "ssh",
  "duration_seconds": 0.234,
  "timeout": 30,
  "timestamp": "2025-10-20T12:34:56.789Z"
}
```

#### Write File
```
POST /api/v1/execution/files/write
```

**Request:**
```json
{
  "path": "/workspace/script.py",
  "content": "print('Hello')"
}
```

#### Read File
```
POST /api/v1/execution/files/read
```

**Request:**
```json
{
  "path": "/workspace/script.py"
}
```

**Response:**
```json
{
  "success": true,
  "path": "/workspace/script.py",
  "content": "print('Hello')",
  "timestamp": "2025-10-20T12:34:56.789Z"
}
```

#### List Supported Languages
```
GET /api/v1/execution/languages
```

**Response:**
```json
{
  "languages": [
    {"language": "python", "extension": "py", "command": "python3 {file}"},
    {"language": "javascript", "extension": "js", "command": "node {file}"},
    ...
  ],
  "count": 12
}
```

### Ops-Center API

#### List Execution Servers
```
GET /api/v1/execution-servers
```

#### Get Default Server
```
GET /api/v1/execution-servers/default
```

#### Create Server
```
POST /api/v1/execution-servers
```

#### Update Server
```
PUT /api/v1/execution-servers/{server_id}
```

#### Delete Server
```
DELETE /api/v1/execution-servers/{server_id}
```

#### Test Connection
```
POST /api/v1/execution-servers/{server_id}/test
```

## Environment Variables

### Brigade (.env)
```bash
# Ops-Center URL for fetching user execution configs
OPS_CENTER_URL=http://ops-center:8000

# API settings
API_HOST=0.0.0.0
API_PORT=8100
LOG_LEVEL=INFO
```

### Docker Compose
```yaml
services:
  unicorn-brigade:
    image: unicorn-brigade:latest
    environment:
      - OPS_CENTER_URL=http://ops-center:8000
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock  # For local Docker execution
```

## Security Considerations

### 1. Path Sanitization
All file paths are validated to prevent directory traversal:
```python
# ❌ Blocked
executor._sanitize_path("../../etc/passwd", "/workspace")

# ✅ Allowed
executor._sanitize_path("/workspace/file.py", "/workspace")
```

### 2. Execution Timeouts
Default: 30 seconds, max: 300 seconds (5 minutes)

### 3. Resource Limits (Docker)
- Memory: 256MB-512MB
- CPU: Limited quota
- Network: Disabled by default

### 4. Encrypted Credentials
- SSH passwords/keys encrypted at rest
- Decrypted only at execution time
- Never exposed in API responses

### 5. User Isolation
- Each user's code runs in their configured environment
- No access to other users' workspaces

## Testing

### Run Unit Tests
```bash
cd /home/muut/Production/UC-Cloud/Unicorn-Brigade
pytest tests/test_remote_executor.py -v
```

### Manual Testing

**1. Test Local Execution:**
```bash
curl -X POST http://localhost:8100/api/v1/execution/execute \
  -H "X-User-ID: test-user" \
  -H "Content-Type: application/json" \
  -d '{"code":"print(\"Hello\")", "language":"python"}'
```

**2. Test with SSH Server:**
First configure SSH server in Ops-Center, then:
```bash
curl -X POST http://localhost:8100/api/v1/execution/execute \
  -H "X-User-ID: real-user-id" \
  -H "Content-Type: application/json" \
  -d '{"code":"import platform; print(platform.node())", "language":"python"}'
```

**3. Test File Operations:**
```bash
# Write
curl -X POST http://localhost:8100/api/v1/execution/files/write \
  -H "X-User-ID: test-user" \
  -H "Content-Type: application/json" \
  -d '{"path":"/workspace/test.txt", "content":"Hello World"}'

# Read
curl -X POST http://localhost:8100/api/v1/execution/files/read \
  -H "X-User-ID: test-user" \
  -H "Content-Type: application/json" \
  -d '{"path":"/workspace/test.txt"}'
```

## Troubleshooting

### Issue: "No module named 'asyncssh'"
**Solution:**
```bash
pip install asyncssh==2.14.2
```

### Issue: "Docker daemon not accessible"
**Solution:**
```bash
sudo usermod -aG docker $USER
# Logout and login again
sudo systemctl restart docker
```

### Issue: "No execution server configured"
**Expected:** Code executes locally (fallback). To use remote server, configure one in Ops-Center.

### Issue: SSH authentication fails
**Solution:**
1. Verify SSH key format (OpenSSH format required)
2. Test connection manually: `ssh -i key.pem user@host`
3. Check firewall rules
4. Use test endpoint: `POST /api/v1/execution-servers/{id}/test`

### Issue: Execution timeout
**Solution:**
- Increase timeout: `{"timeout": 60}`
- Optimize code for faster execution
- Check remote server performance

## Production Deployment

### 1. Update Docker Compose

```yaml
services:
  unicorn-brigade:
    build: ./Unicorn-Brigade
    ports:
      - "8100:8100"
    environment:
      - OPS_CENTER_URL=http://ops-center:8000
      - LOG_LEVEL=INFO
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
    networks:
      - unicorn-network
    restart: unless-stopped
```

### 2. Security Hardening

**Firewall Rules:**
```bash
# Only allow Brigade to connect to Ops-Center
iptables -A OUTPUT -p tcp -d ops-center --dport 8000 -j ACCEPT
```

**Docker Security:**
```yaml
# Use security options
security_opt:
  - no-new-privileges:true
  - seccomp:unconfined
```

### 3. Monitoring

**Health Check:**
```yaml
healthcheck:
  test: ["CMD", "curl", "-f", "http://localhost:8100/api/v1/health"]
  interval: 30s
  timeout: 10s
  retries: 3
```

**Logging:**
```bash
# View execution logs
docker logs -f unicorn-brigade | grep "execution"
```

## Performance Optimization

### 1. Connection Pooling
SSH connections are created per-request. For high-volume scenarios, consider connection pooling.

### 2. Caching
Cache execution results for identical code:
```python
# Future enhancement
result = await executor.execute_code_cached(code, language, user_id)
```

### 3. Async Execution
For long-running tasks, use background execution:
```python
# Future enhancement
task_id = await executor.execute_code_async(code, language, user_id)
result = await executor.get_execution_result(task_id)
```

## Future Enhancements

1. **Kubernetes Support** - Execute in K8s pods
2. **Streaming Output** - Real-time execution output via WebSockets
3. **Multi-file Projects** - Support projects with multiple files
4. **Package Management** - Auto-install dependencies
5. **Execution History** - Track and audit all executions
6. **Result Caching** - Cache identical executions
7. **Interactive Sessions** - REPL-style execution

## Support

**Documentation:**
- Full guide: `/docs/REMOTE_EXECUTION.md`
- Summary: `/docs/REMOTE_EXECUTION_SUMMARY.md`
- Examples: `/docs/examples/remote_execution_example.py`

**Testing:**
- Unit tests: `/tests/test_remote_executor.py`

**Issues:**
Report issues at: https://github.com/unicorn-commander/UC-Cloud/issues

## License

Part of Unicorn Commander Cloud Platform
Copyright © 2025 MagicUnicorn Technologies
