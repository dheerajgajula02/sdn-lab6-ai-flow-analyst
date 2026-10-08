#!/usr/bin/env python3
"""
Interactive Terminal Agent for SDN AI Flow Analyst
===================================================
Demonstrates the autonomous Agentic Tool-Use Loop (ReAct pattern) over MCP tools.
The agent receives a user prompt (e.g. 'What happened at 3 am?'), autonomously
decides which MCP tool to call, inspects telemetry from MongoDB, adjusts its time window,
and synthesizes a plain-English diagnosis.

Usage:
  python3 terminal_agent.py "What happened at 3 am on switch s1?"
  or
  python3 terminal_agent.py  (interactive chat mode)
"""

import sys
import os
import json
import re
from datetime import datetime, timezone

# Import MCP tools directly for local execution or via MCP server
import mcp_server

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# Tool definitions matching standard JSON Schema / MCP format
MCP_TOOL_DEFINITIONS = [
    {
        "name": "list_available_time_ranges",
        "description": "Lists the earliest and latest available telemetry snapshot timestamps stored in MongoDB, and total snapshot count.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "get_latest_telemetry",
        "description": "Retrieves the most recent SDN telemetry snapshot from the network (active flows, per-port stats, and switch status).",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": []
        }
    },
    {
        "name": "query_telemetry_window",
        "description": "Queries historical telemetry snapshots in a custom time window chosen by the agent (e.g. for questions like 'what happened at 3 am?').",
        "parameters": {
            "type": "object",
            "properties": {
                "start_time": {
                    "type": "string",
                    "description": "Beginning of window (e.g. '2026-10-07 03:00', '03:00', or ISO 8601 string)"
                },
                "end_time": {
                    "type": "string",
                    "description": "End of window (e.g. '03:30', defaults to start_time + 1 hour)"
                },
                "minutes_ago": {
                    "type": "integer",
                    "description": "Relative lookback in minutes (e.g. 15 for the last 15 minutes)"
                },
                "limit": {
                    "type": "integer",
                    "description": "Max snapshots to return (default: 10)"
                }
            }
        }
    },
    {
        "name": "detect_anomalies_in_window",
        "description": "Scans snapshots across a time range and automatically identifies traffic floods (DoS spikes in bytes) or rogue DROP flow entries.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_time": {"type": "string", "description": "Optional start time string"},
                "end_time": {"type": "string", "description": "Optional end time string"},
                "minutes_ago": {"type": "integer", "description": "Relative lookback in minutes (default 30)"}
            }
        }
    }
]

TOOL_REGISTRY = {
    "list_available_time_ranges": mcp_server.list_available_time_ranges,
    "get_latest_telemetry": mcp_server.get_latest_telemetry,
    "query_telemetry_window": mcp_server.query_telemetry_window,
    "detect_anomalies_in_window": mcp_server.detect_anomalies_in_window,
}


# Load system prompts dynamically from prompts/ folder
from prompt_loader import get_terminal_agent_system_prompt, load_prompt
SYSTEM_PROMPT = get_terminal_agent_system_prompt()


def parse_and_validate_structured_report(content: str) -> dict:
    """
    Cleans markdown code fences, extracts JSON substring, parses,
    and validates required schema keys: network_health, anomalies_detected, summary.
    """
    clean_text = content.strip()
    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]
    elif clean_text.startswith("```"):
        clean_text = clean_text[3:]
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]
    clean_text = clean_text.strip()

    start_idx = clean_text.find("{")
    end_idx = clean_text.rfind("}")
    if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
        clean_text = clean_text[start_idx:end_idx + 1]

    parsed = json.loads(clean_text)
    required_keys = {"network_health", "anomalies_detected", "summary"}
    if not required_keys.issubset(parsed.keys()):
        raise ValueError(f"Missing required keys in JSON: {required_keys - set(parsed.keys())}")
    return parsed


def display_structured_report(report: dict) -> None:
    """Formats and prints the structured report with separate sections (Objective 3)."""
    print("\n" + "=" * 65)
    print("OBJECTIVE 3: STRUCTURED AI NETWORK HEALTH REPORT")
    print("=" * 65)
    health = str(report.get("network_health", "UNKNOWN")).upper()
    print(f"\n[+] NETWORK HEALTH: {health}")

    anomalies = report.get("anomalies_detected", [])
    print(f"\n[+] ANOMALIES DETECTED ({len(anomalies)} found):")
    if anomalies:
        for idx, a in enumerate(anomalies, 1):
            sev = str(a.get("severity", "unknown")).upper()
            dev = a.get("affected_device", "unknown")
            atype = a.get("type", "unknown")
            desc = a.get("description", "No description provided.")
            print(f"    {idx}. [{sev}] {atype} on {dev}")
            print(f"       Details: {desc}")
    else:
        print("    None. Network operating within nominal baseline parameters.")

    print(f"\n[+] EXECUTIVE SUMMARY:")
    print(f"    {report.get('summary', 'N/A')}")
    print("\n[+] RAW STRUCTURED JSON RETURN:")
    print(json.dumps(report, indent=2))
    print("=" * 65 + "\n")


def execute_tool(tool_name: str, arguments: dict) -> str:
    """Executes the requested MCP tool function."""
    func = TOOL_REGISTRY.get(tool_name)
    if not func:
        return f"Error: Unknown tool '{tool_name}'."
    try:
        return str(func(**arguments))
    except Exception as e:
        return f"Error executing tool '{tool_name}': {e}"


# ==============================================================================
# Model Dispatchers with Function / Tool Calling Support
# ==============================================================================
# ==============================================================================
# Model Dispatcher: Universal OpenAI-Compatible Agentic Loop
# Compatible with Xiaomi MiMo, DeepSeek, OpenCode, OpenAI, Ollama, and vLLM
# ==============================================================================
DEFAULT_BASE_URL = os.environ.get("OPENAI_BASE_URL") or os.environ.get("MIMO_BASE_URL", "https://token-plan-sgp.xiaomimimo.com/v1")
DEFAULT_API_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("MIMO_API_KEY", "")
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL") or os.environ.get("MIMO_MODEL", "mimo-v2.6-flash")


def run_agentic_loop(
    user_query: str,
    base_url: str = DEFAULT_BASE_URL,
    api_key: str = DEFAULT_API_KEY,
    model: str = DEFAULT_MODEL,
    max_turns: int = 5,
    include_architecture: bool = False
) -> dict:
    """
    Executes the ReAct Agentic Loop using the universal OpenAI Chat Completions protocol.
    Works natively with Xiaomi MiMo, DeepSeek, OpenCode, OpenAI, and local engines.
    """
    import requests

    print("\n" + "=" * 65)
    print(f"USER QUERY: {user_query}")
    print("=" * 65)
    print(f"[*] Provider Endpoint: {base_url} (model: {model})")
    if include_architecture:
        print("[*] Injected Network Architecture & Topology Context into System Prompt.")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    tools = [{"type": "function", "function": t} for t in MCP_TOOL_DEFINITIONS]
    endpoint = f"{base_url.rstrip('/')}/chat/completions"

    system_content = get_terminal_agent_system_prompt(include_architecture=include_architecture)
    messages = [
        {"role": "system", "content": system_content},
        {"role": "user", "content": user_query}
    ]

    for turn in range(1, max_turns + 1):
        payload = {
            "model": model,
            "messages": messages,
            "tools": tools,
            "tool_choice": "auto",
            "temperature": 0.2
        }

        resp = requests.post(endpoint, headers=headers, json=payload, timeout=40)
        resp.raise_for_status()
        choice = resp.json()["choices"][0]
        message = choice["message"]
        messages.append(message)

        reasoning = message.get("reasoning_content")
        if reasoning:
            print(f"\n🧠 [Model Reasoning - Turn {turn}]:\n{reasoning.strip()}\n")

        tool_calls = message.get("tool_calls", [])
        if not tool_calls:
            raw_content = message.get("content", "")
            try:
                report = parse_and_validate_structured_report(raw_content)
            except Exception as e:
                print(f"[!] Warning: Initial JSON parse failed ({e}). Performing 1x defensive retry...")
                retry_messages = list(messages)
                retry_messages.append({
                    "role": "user",
                    "content": load_prompt("defensive_retry.md", error=str(e))
                })
                retry_resp = requests.post(
                    endpoint,
                    headers=headers,
                    json={"model": model, "messages": retry_messages, "temperature": 0.1},
                    timeout=30
                )
                retry_resp.raise_for_status()
                raw_retry = retry_resp.json()["choices"][0]["message"].get("content", "")
                report = parse_and_validate_structured_report(raw_retry)

            display_structured_report(report)
            return report

        # Execute each tool requested by the model
        for tc in tool_calls:
            t_name = tc["function"]["name"]
            t_args = json.loads(tc["function"].get("arguments", "{}"))
            print(f"🤖 [Agent Tool Call - Turn {turn}]: {t_name}({json.dumps(t_args)})")

            t_result = execute_tool(t_name, t_args)
            preview = t_result[:180] + "..." if len(t_result) > 180 else t_result
            print(f"   <- [Tool Output: {len(t_result)} chars] {preview.strip()}")

            messages.append({
                "role": "tool",
                "tool_call_id": tc["id"],
                "content": t_result
            })

    print("[!] Reached maximum agentic loop turns without final synthesis.")
    fallback = {
        "network_health": "warning",
        "anomalies_detected": [],
        "summary": "Agent reached max turns before synthesizing final report."
    }
    display_structured_report(fallback)
    return fallback


if __name__ == "__main__":
    cli_args = sys.argv[1:]
    include_arch = "--arch" in cli_args
    filtered_args = [a for a in cli_args if a != "--arch"]

    if filtered_args:
        query = " ".join(filtered_args)
        run_agentic_loop(query, include_architecture=include_arch)
    else:
        print("=" * 65)
        print("SDN AI Flow Analyst - Interactive Terminal Agent")
        if include_arch:
            print("[*] Option '--arch' enabled: Topology context will be injected into prompts.")
        print("=" * 65)
        print("Example queries you can ask:")
        print("  - What is the latest state of the network?")
        print("  - What happened in the last 15 minutes?")
        print("  - Are there any DoS attacks or high-volume traffic floods?")
        print("Flags supported:")
        print("  --arch : Appends architecture.md context to agent system prompt")
        print("Type 'exit' to quit.\n")

        while True:
            try:
                user_q = input("\n[Enter Question] > ").strip()
                if not user_q or user_q.lower() in ("exit", "quit"):
                    break
                run_agentic_loop(user_q, include_architecture=include_arch)
            except (KeyboardInterrupt, EOFError):
                break
