# Remote Code Execution in Unicorn Brigade

## Overview

Unicorn Brigade now supports remote code execution on user-configured servers. When Brigade agents need to execute code, they can run it on:

1. **SSH Servers** - Execute code on any SSH-accessible server
2. **Docker Hosts** - Run code in isolated Docker containers
3. **Local Execution** - Fallback to Brigade's own server (sandboxed in Docker)

## Architecture

```
┌─────────────────────┐
│  Unicorn Brigade    │
│   (CodeAgent)       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  RemoteExecutor     │
│  - Get user config  │
│  - Route execution  │
└──────────┬──────────┘
           │
     ┌─────┴─────┐
     ▼           ▼
┌─────────┐  ┌─────────┐  ┌─────────┐
│   SSH   │  │ Docker  │  │  Local  │
│ Server  │  │  Host   │  │ (Docker)│
└─────────┘  └─────────┘  └─────────┘
```

## Configuration

### 1. Configure Execution Server in Ops-Center

Users configure their execution servers through the Ops-Center API:

**SSH Server Example:**
```bash
curl -X POST https://unicorncommander.ai/api/v1/execution-servers \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{
    "name": "My Dev Server",
    "server_type": "ssh",
    "connection_config": {
      "host": "dev.example.com",
      "port": 22,
      "username": "developer",
      "auth_method": "key",
      "private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\n...",
      "workspaceRoot": "/home/developer/magicode"
    },
    "is_default": true
  }'
```

**Docker Server Example:**
```bash
curl -X POST https://unicorncommander.ai/api/v1/execution-servers \
  -H "Cookie: session=..." \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Local Docker",
    "server_type": "docker",
    "connection_config": {
      "image": "python:3.11-slim",
      "memoryLimit": "512m",
      "cpuQuota": 100000
    },
    "is_default": true
  }'
```

### 2. Brigade Automatically Uses User's Configuration

When a CodeAgent executes code, it:
1. Fetches the user's default execution server from Ops-Center
2. Routes the code execution to that server
3. Returns results to the user

## Supported Languages

The RemoteExecutor supports multiple programming languages:

| Language   | Extension | Command                                    |
|------------|-----------|---------------------------------------------|
| Python     | `.py`     | `python3 {file}`                           |
| JavaScript | `.js`     | `node {file}`                              |
| TypeScript | `.ts`     | `ts-node {file}`                           |
| Bash       | `.sh`     | `bash {file}`                              |
| Ruby       | `.rb`     | `ruby {file}`                              |
| Go         | `.go`     | `go run {file}`                            |
| Rust       | `.rs`     | `rustc {file} -o /tmp/output && /tmp/output`|
| Java       | `.java`   | `javac {file} && java ClassName`           |
| PHP        | `.php`    | `php {file}`                               |
| Perl       | `.pl`     | `perl {file}`                              |
| R          | `.r`      | `Rscript {file}`                           |
| Julia      | `.jl`     | `julia {file}`                             |

## Usage in Brigade Agents

### CodeAgent - Execute Code

```python
from app.agents.code import CodeAgent

agent = CodeAgent(memory_manager, llm_client)

# Execute Python code
result = await agent.execute_code(
    code="print('Hello from remote server!')",
    language="python",
    user_id="user-123",
    timeout=30
)

print(f"Success: {result['success']}")
print(f"Output: {result['output']}")
print(f"Execution Type: {result['execution_type']}")  # ssh, docker, or local
```

### CodeAgent - File Operations

```python
# Write file to remote server
success = await agent.write_file(
    path="/workspace/script.py",
    content="print('Hello World')",
    user_id="user-123"
)

# Read file from remote server
content = await agent.read_file(
    path="/workspace/script.py",
    user_id="user-123"
)
```

## Security Features

### 1. Path Sanitization
All file paths are sanitized to prevent directory traversal attacks:

```python
# ❌ This will raise ValueError
executor._sanitize_path("../../etc/passwd", "/tmp/workspace")

# ✅ This is safe
executor._sanitize_path("/tmp/workspace/file.py", "/tmp/workspace")
```

### 2. Execution Timeouts
All code execution has configurable timeouts (default: 30 seconds):

```python
result = await executor.execute_code(
    language="python",
    code="import time; time.sleep(100)",
    timeout=5  # Will timeout after 5 seconds
)
```

### 3. Resource Limits (Docker)
Docker containers are created with resource limits:

- **Memory**: 256MB-512MB (configurable)
- **CPU**: Limited quota (configurable)
- **Network**: Disabled by default (`network_mode="none"`)

### 4. Encrypted Credentials
SSH passwords and private keys are encrypted using Ops-Center's encryption service before storage.

### 5. Sandboxed Local Execution
When no remote server is configured, code runs in isolated Docker containers with:
- No network access
- Limited resources
- Read-only workspace mounting

## API Endpoints (Ops-Center)

### List Execution Servers
```
GET /api/v1/execution-servers
```

### Get Default Server
```
GET /api/v1/execution-servers/default
```

### Create Execution Server
```
POST /api/v1/execution-servers
```

### Update Execution Server
```
PUT /api/v1/execution-servers/{server_id}
```

### Delete Execution Server
```
DELETE /api/v1/execution-servers/{server_id}
```

### Test Connection
```
POST /api/v1/execution-servers/{server_id}/test
```

## Execution Flow

```mermaid
sequenceDiagram
    participant User
    participant Brigade
    participant RemoteExecutor
    participant OpsCenter
    participant RemoteServer

    User->>Brigade: Execute code via CodeAgent
    Brigade->>RemoteExecutor: execute_code(language, code, user_id)
    RemoteExecutor->>OpsCenter: GET /api/v1/execution-servers/default
    OpsCenter-->>RemoteExecutor: Server config (type, connection)

    alt SSH Server
        RemoteExecutor->>RemoteServer: SSH connect
        RemoteExecutor->>RemoteServer: SFTP write code file
        RemoteExecutor->>RemoteServer: Execute command
        RemoteServer-->>RemoteExecutor: Output + exit code
        RemoteExecutor->>RemoteServer: Cleanup temp file
    else Docker Server
        RemoteExecutor->>RemoteServer: docker run with code volume
        RemoteServer-->>RemoteExecutor: Container output + exit code
    else Local (fallback)
        RemoteExecutor->>RemoteExecutor: docker run locally
        RemoteExecutor-->>RemoteExecutor: Container output
    end

    RemoteExecutor-->>Brigade: Execution result
    Brigade-->>User: Result with output/errors
```

## Error Handling

### Connection Errors
If connection to the configured server fails, the error is returned to the user:

```json
{
  "success": false,
  "error": "SSH connection failed: Connection timeout",
  "exit_code": -1,
  "execution_type": "ssh"
}
```

### Execution Errors
If code execution fails, the error output is captured:

```json
{
  "success": false,
  "output": "Traceback (most recent call last):\n  File...",
  "error": "Python SyntaxError",
  "exit_code": 1,
  "execution_type": "ssh"
}
```

### Timeout Errors
If execution exceeds the timeout:

```json
{
  "success": false,
  "error": "Execution timeout after 30 seconds",
  "exit_code": -1,
  "execution_type": "ssh"
}
```

## Testing

Run the test suite:

```bash
cd /home/muut/Production/UC-Cloud/Unicorn-Brigade
pytest tests/test_remote_executor.py -v
```

## Environment Variables

Configure Brigade with:

```bash
# In .env or docker-compose.yml
OPS_CENTER_URL=http://ops-center:8000
```

## Future Enhancements

### Planned Features:
1. **Kubernetes Support** - Execute code in Kubernetes pods
2. **Result Caching** - Cache execution results for identical code
3. **Execution History** - Track and log all code executions
4. **Multi-file Execution** - Support projects with multiple files
5. **Package Installation** - Auto-install dependencies before execution
6. **Real-time Streaming** - Stream execution output in real-time
7. **Interactive Sessions** - Support REPL-style execution

## Troubleshooting

### Issue: "No execution server configured"
**Solution**: Configure a default execution server in Ops-Center, or code will execute locally.

### Issue: SSH connection fails
**Solution**:
1. Test connection: `POST /api/v1/execution-servers/{id}/test`
2. Verify SSH credentials and firewall rules
3. Check private key format (OpenSSH format required)

### Issue: Docker execution fails
**Solution**:
1. Ensure Docker is installed and running
2. Check Docker daemon permissions
3. Verify image exists: `docker pull python:3.11-slim`

### Issue: Timeout errors
**Solution**:
1. Increase timeout: `execute_code(..., timeout=60)`
2. Optimize code for faster execution
3. Use async/background execution for long-running tasks

## License

Part of Unicorn Commander Cloud Platform - MagicUnicorn Technologies
