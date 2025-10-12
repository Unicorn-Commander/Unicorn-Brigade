# UC2 Tool System

A comprehensive tool system for Unicorn Command & Control (UC2) with modular architecture, security controls, and version tracking.

## 🏗️ Architecture Overview

```
core/tools/
├── internal/              # Core internal tools
│   ├── calculator.js      # Math operations
│   ├── webSearch.js       # Web search via APIs
│   ├── filesystem.js      # Sandboxed file operations
│   └── database.js        # Prisma database queries
├── external/              # Third-party tools (empty)
├── scripts/               # Management utilities
│   ├── sync-tools.js      # Tool synchronization
│   ├── validate-registry.js # Registry validation
│   └── test-tools.js      # Automated testing
├── registry.json          # Master tool catalog
└── README.md              # This file

agents/sample-agent/
├── agent.json             # Agent configuration
├── tools/                 # Agent-specific tools
│   ├── manifest.json      # Tool manifest
│   ├── calculator.js      # Synced tools
│   ├── webSearch.js
│   ├── filesystem.js
│   └── database.js
├── workspace/             # Agent workspace
└── config/
    └── prompts.json       # Agent prompts
```

## 🔧 Available Tools

### 🧮 Calculator Tool
- **Purpose**: Safe mathematical calculations
- **Permissions**: `basic`
- **Features**:
  - Arithmetic operations (+, -, *, /, %, **)
  - Trigonometric functions (sin, cos, tan)
  - Mathematical functions (sqrt, log)
  - Configurable precision
  - Input sanitization and validation

**Example**:
```javascript
await calculator.execute({
  expression: "Math.sin(Math.PI / 2) + Math.sqrt(16)",
  precision: 4
});
// Result: { success: true, result: 5.0000 }
```

### 🔍 Web Search Tool
- **Purpose**: Search the web using multiple engines
- **Permissions**: `network`, `api`
- **Engines**: DuckDuckGo, SearX, Google, Bing
- **Features**:
  - Multiple search engine support
  - Safe search filtering
  - Result limiting and pagination
  - Language preferences
  - Fallback mechanisms

**Example**:
```javascript
await webSearch.execute({
  query: "artificial intelligence 2025",
  engine: "duckduckgo",
  limit: 5,
  safe: true
});
```

### 📁 Filesystem Tool
- **Purpose**: Sandboxed file and directory operations
- **Permissions**: `filesystem`, `read`, `write`
- **Operations**: read, write, append, delete, list, exists, info, mkdir, copy, move
- **Security**: Path traversal protection, sandbox isolation
- **Features**:
  - Multiple encoding support (utf8, base64, binary)
  - Checksum verification
  - Directory recursion
  - File metadata access

**Example**:
```javascript
await filesystem.execute({
  operation: "write",
  path: "data/report.txt",
  content: "Analysis complete",
  encoding: "utf8"
});
```

### 🗄️ Database Tool
- **Purpose**: Safe Prisma database queries
- **Permissions**: `database`, `read`, `write`
- **Models**: agent, agentMessage, agentTask, orchestration, memory, tool, workflow, aiProvider, user, session
- **Features**:
  - CRUD operations with validation
  - Query result limiting
  - Sensitive field filtering
  - Permission-based access
  - SQL injection prevention

**Example**:
```javascript
await database.execute({
  operation: "findMany",
  model: "agent",
  where: { status: "active" },
  take: 10
});
```

## 🚀 Quick Start

### 1. Initialize Tool System
```bash
cd core/tools
node scripts/validate-registry.js  # Validate configuration
node scripts/test-tools.js         # Test all tools
```

### 2. Sync Tools to Agent
```bash
# Sync all tools to all agents
node scripts/sync-tools.js

# Sync specific agent
node scripts/sync-tools.js --agent sample-agent

# Dry run (preview changes)
node scripts/sync-tools.js --dry-run
```

### 3. Use Tools in Code

#### Backend Integration
```javascript
const { getToolExecutor } = require('./backend/services/toolExecutor');

const toolExecutor = getToolExecutor();
await toolExecutor.initialize();

// Execute a tool
const result = await toolExecutor.executeTool('calculator', {
  expression: '2 + 3 * 4'
}, {
  userId: 'user123',
  agentId: 'agent456'
});
```

#### Direct Tool Usage
```javascript
const Calculator = require('./core/tools/internal/calculator');
const calc = new Calculator();

const result = await calc.execute({
  expression: 'Math.sqrt(25) + 10',
  precision: 2
});
console.log(result.result); // 15.00
```

## 📊 Management Commands

### Validation
```bash
# Validate entire registry
node scripts/validate-registry.js

# Check specific tool implementation
node -e "
const Tool = require('./internal/calculator.js');
const tool = new Tool();
console.log(tool.validate());
"
```

### Testing
```bash
# Test all tools
node scripts/test-tools.js

# Test specific tool
node scripts/test-tools.js --tool calculator

# Verbose output
node scripts/test-tools.js --verbose
```

### Synchronization
```bash
# Sync all agents
node scripts/sync-tools.js

# Sync specific agent
node scripts/sync-tools.js --agent sample-agent

# Sync specific tool across all agents
node scripts/sync-tools.js --tool calculator

# Force sync even if versions match
node scripts/sync-tools.js --force

# Only update existing tools, don't add new ones
node scripts/sync-tools.js --update-only
```

## 🔒 Security Features

### Input Validation
- JSON schema validation for all parameters
- Type checking and sanitization
- Length and format restrictions
- Enum value validation

### Sandboxing
- **Filesystem**: Restricted to sandbox directories only
- **Calculator**: Safe expression evaluation with Function constructor
- **Database**: Query parameter sanitization and result filtering
- **Web Search**: Request timeout and rate limiting

### Permission System
- **Basic**: calculator (no external dependencies)
- **Network**: webSearch (external API calls)
- **Filesystem**: filesystem (file system access)
- **Database**: database (database access)
- **Read/Write**: granular access controls

### Rate Limiting
- Per-tool limits (100/hour)
- Per-user limits (1000/hour)
- Global limits (10000/hour)
- Automatic cleanup of old counters

## 📈 Monitoring & Analytics

### Execution Tracking
```javascript
const toolExecutor = getToolExecutor();

// Get execution history
const history = toolExecutor.getExecutionHistory(50);

// Get performance statistics
const stats = toolExecutor.getExecutionStats();
console.log(stats);
// {
//   totalTools: 4,
//   executionsLast24h: 156,
//   executionsLastHour: 23,
//   successRate: 98.5,
//   toolUsage: { calculator: 45, webSearch: 32, ... },
//   averageExecutionTime: 127.5
// }
```

### Tool Information
```javascript
// Get available tools for user
const tools = toolExecutor.getAvailableTools(context);

// Get specific tool info
const info = toolExecutor.getToolInfo('calculator');
```

## 🔄 Development Workflow

### Adding New Tools

1. **Create Tool Implementation**
```javascript
// core/tools/internal/myTool.js
class MyTool {
  constructor() {
    this.name = 'myTool';
    this.version = '1.0.0';
    this.description = 'My custom tool';
    // ... other properties
  }

  async execute(params, context) {
    // Tool implementation
  }

  validate() {
    // Validation logic
  }
}
module.exports = MyTool;
```

2. **Update Registry**
```json
{
  "tools": {
    "myTool": {
      "name": "myTool",
      "version": "1.0.0",
      "type": "internal",
      "category": "custom",
      "description": "My custom tool",
      "path": "internal/myTool.js",
      // ... other metadata
    }
  }
}
```

3. **Validate and Test**
```bash
node scripts/validate-registry.js
node scripts/test-tools.js --tool myTool
```

4. **Sync to Agents**
```bash
node scripts/sync-tools.js
```

### Tool Updates

1. **Update Implementation**: Modify tool file
2. **Update Version**: Increment version in both tool and registry
3. **Validate Changes**: Run validation and tests
4. **Sync Changes**: Sync updated tools to agents

## 🏷️ Version Tracking

The sync utility automatically tracks:
- Tool versions and checksums
- Last sync timestamps
- Agent-specific tool versions
- Change history

Version information is stored in `core/tools/.versions.json`:
```json
{
  "lastSync": "2025-09-25T20:57:36.691Z",
  "tools": {
    "calculator@1.0.0": {
      "checksum": "sha256:abc123...",
      "lastSynced": "2025-09-25T20:57:36.691Z",
      "agent": "sample-agent"
    }
  }
}
```

## 🎯 Best Practices

### Tool Development
- Always implement `validate()` method
- Include comprehensive error handling
- Provide clear parameter schemas
- Add usage examples
- Follow security guidelines
- Test thoroughly before deployment

### Agent Configuration
- Only enable tools that are actually needed
- Configure tool permissions appropriately
- Set resource limits (file sizes, result counts)
- Provide tool-specific configuration
- Test tool combinations

### Security
- Never bypass sandboxing restrictions
- Validate all external inputs
- Use appropriate permission levels
- Monitor tool usage patterns
- Keep tools updated

## 🐛 Troubleshooting

### Common Issues

**Tool Not Found**
```bash
# Verify tool is in registry
cat registry.json | grep "toolName"

# Check if tool file exists
ls -la internal/toolName.js
```

**Sync Failures**
```bash
# Check agent configuration
cat ../agents/agent-name/agent.json

# Validate permissions
node scripts/validate-registry.js

# Force sync
node scripts/sync-tools.js --force
```

**Permission Errors**
- Check user role and permissions
- Verify tool permission requirements
- Review permission matrix in registry

**Performance Issues**
- Check rate limiting settings
- Monitor execution statistics
- Review tool complexity and timeouts

## 📚 API Reference

See individual tool files for detailed API documentation. All tools follow the standard interface:

```javascript
class ToolInterface {
  constructor()
  async execute(params, context)
  getInfo()
  validate()
}
```

## 🤝 Contributing

1. Follow existing code patterns
2. Add comprehensive tests
3. Update registry entries
4. Validate all changes
5. Document new features

---

**UC2 Tool System v1.0.0** - Built for robust, secure, and scalable AI agent operations.