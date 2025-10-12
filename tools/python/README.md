# Tool Architecture

This document outlines the architecture for how agents discover, use, and acquire tools within the system.

## Three-Tiered Tool System

The architecture is composed of three main tiers, providing a balance of reusability, specialization, and security.

### 1. The Central Tool Repository (This Folder)

*   **What it is:** This `/tools` directory is the central, shared repository for all common tools. It acts as the single source of truth for reusable capabilities.
*   **Contents:** It contains the source code for well-tested, generic tools (e.g., `web_scraper.py`, `file_manager.py`).
*   **Purpose:** To promote code reuse, simplify maintenance, and provide a library of standard capabilities available to all agents.

### 2. The Agent's Tool Profile (`tools.json`)

*   **What it is:** A `tools.json` file located in each agent's specific directory.
*   **Contents:** This file does **not** contain the tool's code. It contains a JSON list of **names** of the tools that the agent is authorized and configured to use. This list can reference tools from both the Central Repository and the agent's own custom tools.
*   **Purpose:** It serves as a manifest and a security control layer. The Agent Host uses this list to determine which tool implementations to provide to the agent at runtime.

**Example `tools.json`:**
```json
{
  "tools": [
    "file_manager",         // From Central Repository
    "shell_command_runner", // From Central Repository
    "case_file_parser"      // From this agent's custom_tools/ folder
  ]
}
```

### 3. Agent-Specific Custom Tools

*   **What it is:** A sub-directory within an agent's own folder, e.g., `/domains/legal/my_agent/custom_tools/`.
*   **Contents:** The actual source code for tools that are unique and highly specialized to that one agent.
*   **Purpose:** To allow for the development of an agent's unique skills without cluttering the central repository with single-use tools.

## Dynamic Tool Acquisition

This architecture supports dynamic capabilities, allowing an agent to request tools it doesn't currently have in its profile.

**Workflow:**

1.  **Need Identification:** An agent, while processing a task, determines it needs a tool not listed in its `tools.json` (e.g., `code_interpreter`).
2.  **Request:** The agent makes a formal request to its supervising Host Interface: "I require the `code_interpreter` tool to proceed."
3.  **Mediation:** The Host Interface intercepts the request and can apply its own logic:
    *   Verify the tool exists in the Central Tool Repository.
    *   Consult a permissions policy to see if this agent *type* is allowed to use such a tool.
    *   **Ask the user for real-time approval.**
4.  **Grant/Deny:** If approved, the Host dynamically provides the agent with access to the tool for the current task. The Host can also offer to permanently update the agent's `tools.json` profile for future use.
