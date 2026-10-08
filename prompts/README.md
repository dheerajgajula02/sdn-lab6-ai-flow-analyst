# SDN AI Flow Analyst - Prompt Directory

This directory stores all natural language prompts, system instructions, and schema definitions decoupled from Python execution code.

## Files

| File | Used By | Description |
|---|---|---|
| `terminal_agent_system.md` | `terminal_agent.py` | Main system prompt instructing autonomous agent on tool calling and JSON format. |
| `defensive_retry.md` | `terminal_agent.py`, `ai_analyst.py` | 1x defensive retry prompt injected when JSON validation fails. |
| `structured_schema.md` | `ai_analyst.py` | Strict JSON schema requirement for Objective 3. |
| `text_analyst_system.md` | `ai_analyst.py` | System prompt for Objective 2 free-text analyst. |
| `text_analyst_user.md` | `ai_analyst.py` | User prompt template for Objective 2. |
| `structured_analyst_system.md` | `ai_analyst.py` | System prompt for Objective 3 structured JSON analyst. |
| `structured_analyst_user.md` | `ai_analyst.py` | User prompt template for Objective 3. |
| `mcp_server_instructions.md` | `mcp_server.py` | Instructions exposed to LLM clients by the FastMCP server. |

## Dynamic Appending

Prompts are read dynamically via `prompt_loader.py`. If additional contextual knowledge (such as `skills/sdn-flow-analyst/references/architecture.md`) needs to be appended to the agent's system prompt, it can be passed via `include_architecture=True`.
