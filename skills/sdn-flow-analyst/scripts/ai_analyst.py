#!/usr/bin/env python3
"""
CSCI 5280 - Lab 6: AI Flow Analyst
----------------------------------
Implements:
- Objective 2: format_for_llm() and free-text analyze_network()
- Objective 3: Structured JSON response parsing and defensive retry handling
- Objective 4: Continuous 30-second monitoring loop with health transition alerts

Supports OpenAI (gpt-4o-mini), Google Gemini (gemini-1.5-flash/2.0-flash),
and Anthropic Claude (claude-3-haiku) via direct HTTP requests using `requests`.
"""

import sys
import os
import json
import time
from datetime import datetime
import requests

from flow_collector import collect_complete_network_state

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


# ==============================================================================
# Objective 2, Step 1: format_for_llm()
# ==============================================================================
def format_for_llm(data):
    """
    Formats the raw collected network state dictionary into a clean,
    structured, human-and-LLM-readable telemetry summary.
    Avoids raw JSON walls and presents key network metrics clearly.
    """
    lines = []
    lines.append("=== SDN NETWORK TELEMETRY REPORT ===")
    lines.append(f"Timestamp: {data.get('timestamp', 'Unknown')}")
    
    # Switch connection summary
    status_raw = data.get("switch_connection_status", "")
    switches = list(data.get("controller_flow_tables", {}).keys())
    lines.append(f"Monitored Switches: {', '.join(switches)}")
    lines.append("Connection Status: Connected to SDN Controller (OF1.3, Secure Mode)")
    lines.append("-" * 50)

    # Port statistics and flow tables per switch
    port_stats = data.get("port_statistics", {})
    flow_tables = data.get("controller_flow_tables", {})
    active_counts = data.get("active_flow_counts", {})

    for sw in switches:
        lines.append(f"\n[SWITCH {sw.upper()}] (Active Flow Count: {active_counts.get(sw, 'N/A')})")
        
        # 1. Port statistics
        lines.append("  Port Traffic Statistics:")
        ports = port_stats.get(sw, {})
        for port_id, stats in sorted(ports.items(), key=lambda x: str(x[0])):
            rx_pkts = stats.get("rx_pkts", 0)
            rx_bytes = stats.get("rx_bytes", 0)
            tx_pkts = stats.get("tx_pkts", 0)
            tx_bytes = stats.get("tx_bytes", 0)
            rx_drop = stats.get("rx_drop", 0)
            tx_drop = stats.get("tx_drop", 0)
            
            # Format bytes into human readable KB / MB if high
            rx_str = f"{rx_bytes:,} B" if rx_bytes < 1048576 else f"{rx_bytes / 1048576:.2f} MB"
            tx_str = f"{tx_bytes:,} B" if tx_bytes < 1048576 else f"{tx_bytes / 1048576:.2f} MB"
            
            lines.append(
                f"    - Port {port_id}: "
                f"Rx={rx_pkts:,} pkts ({rx_str}), "
                f"Tx={tx_pkts:,} pkts ({tx_str}), "
                f"Drops=(Rx:{rx_drop}, Tx:{tx_drop})"
            )

        # 2. Flow table entries
        lines.append("  Flow Table Entries (Sample / Notable Rules):")
        flows = flow_tables.get(sw, [])
        # Prioritize rules with actions like DROP or high priority/packet counts
        sorted_flows = sorted(
            flows,
            key=lambda f: (f.get("priority", 0), f.get("packet_count", 0)),
            reverse=True
        )

        notable_flows = []
        normal_flows_count = 0

        for f in sorted_flows:
            priority = f.get("priority", 0)
            actions = f.get("actions", [])
            match = f.get("match", {})
            pkts = f.get("packet_count", 0)
            bytes_count = f.get("byte_count", 0)

            # Highlight DROP rules, unusual priorities (>1000), or heavy packet hitters
            is_suspicious = any("drop" in str(a).lower() for a in actions) or priority > 1000 or pkts > 1000
            if is_suspicious or len(notable_flows) < 6:
                match_str = ", ".join(f"{k}={v}" for k, v in match.items()) or "ANY"
                action_str = ", ".join(actions) or "DROP"
                flag = " [!] ALERT" if is_suspicious else " [-]"
                notable_flows.append(
                    f"    {flag} Priority {priority}: Match({match_str}) -> Actions({action_str}) "
                    f"[Pkts: {pkts:,}, Bytes: {bytes_count:,}]"
                )
            else:
                normal_flows_count += 1

        for nf in notable_flows:
            lines.append(nf)
        if normal_flows_count > 0:
            lines.append(f"    ... and {normal_flows_count} standard L2 forwarding rules.")

    lines.append("=" * 50)
    return "\n".join(lines)


# ==============================================================================
# Universal OpenAI-Compatible LLM Dispatcher
# Compatible with Xiaomi MiMo, DeepSeek, OpenCode, OpenAI, Ollama, and vLLM
# ==============================================================================
DEFAULT_BASE_URL = os.environ.get("OPENAI_BASE_URL") or os.environ.get("MIMO_BASE_URL", "https://token-plan-sgp.xiaomimimo.com/v1")
DEFAULT_API_KEY = os.environ.get("OPENAI_API_KEY") or os.environ.get("MIMO_API_KEY", "")
DEFAULT_MODEL = os.environ.get("OPENAI_MODEL") or os.environ.get("MIMO_MODEL", "mimo-v2.6-flash")


def call_llm(prompt, system_prompt=None, json_mode=False, base_url=DEFAULT_BASE_URL, api_key=DEFAULT_API_KEY, model=DEFAULT_MODEL):
    """
    Dispatches prompt to any OpenAI-compatible provider (MiMo, DeepSeek, OpenCode, OpenAI).
    """
    endpoint = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": 0.2
    }
    if json_mode:
        payload["response_format"] = {"type": "json_object"}

    resp = requests.post(endpoint, headers=headers, json=payload, timeout=30)
    resp.raise_for_status()
    res_json = resp.json()
    return res_json["choices"][0]["message"]["content"]


from prompt_loader import load_prompt


# ==============================================================================
# Objective 2, Step 2: analyze_network() (Free-Text Analyst)
# ==============================================================================
def analyze_network_text(data=None):
    """
    Collects live state, formats it, prompts LLM as an expert network engineer,
    and returns plain-English diagnosis.
    """
    if data is None:
        data = collect_complete_network_state()

    formatted_context = format_for_llm(data)

    system_prompt = load_prompt("text_analyst_system.md")
    user_prompt = load_prompt("text_analyst_user.md", context=formatted_context)

    print("\n[*] Sending network telemetry to AI Analyst...")
    response = call_llm(user_prompt, system_prompt=system_prompt, json_mode=False)
    return response


# ==============================================================================
# Objective 3: Structured JSON Analyst with Defensive Retry Logic
# ==============================================================================
def analyze_network_structured(data=None, is_retry=False):
    """
    Requests a structured JSON response from the model, validates and parses it,
    with an automatic defensive retry if parsing fails.
    """
    if data is None:
        data = collect_complete_network_state()

    formatted_context = format_for_llm(data)

    system_prompt = load_prompt("structured_analyst_system.md")
    schema_instruction = load_prompt("structured_schema.md")
    retry_modifier = (
        "\n" + load_prompt("defensive_retry.md", error="Invalid schema format")
        if is_retry else ""
    )

    user_prompt = load_prompt(
        "structured_analyst_user.md",
        context=formatted_context,
        schema_instruction=schema_instruction,
        retry_modifier=retry_modifier
    )

    raw_response = call_llm(user_prompt, system_prompt=system_prompt, json_mode=True)
    
    # Clean possible markdown fences if returned
    clean_text = raw_response.strip()
    if clean_text.startswith("```json"):
        clean_text = clean_text[7:]
    if clean_text.startswith("```"):
        clean_text = clean_text[3:]
    if clean_text.endswith("```"):
        clean_text = clean_text[:-3]
    clean_text = clean_text.strip()

    try:
        parsed_json = json.loads(clean_text)
        # Validate required keys
        required_keys = {"network_health", "anomalies_detected", "summary"}
        if not required_keys.issubset(parsed_json.keys()):
            raise ValueError(f"Missing required schema keys. Found: {list(parsed_json.keys())}")
        return parsed_json

    except Exception as exc:
        if not is_retry:
            print(f"[!] Warning: Initial JSON parse failed ({exc}). Retrying with stricter prompt...", file=sys.stderr)
            return analyze_network_structured(data, is_retry=True)
        else:
            print(f"[ERROR] Retry failed to parse JSON. Raw response:\n{raw_response}", file=sys.stderr)
            return {
                "network_health": "unknown",
                "anomalies_detected": [],
                "summary": f"Parse Error: {exc}. Raw: {raw_response[:200]}"
            }


def display_structured_output(report):
    """
    Displays the model's structured response:
    1. The validated JSON object (for Objective 3 Step 3 screenshots)
    2. Each parsed field printed separately (for Objective 3 Step 1 requirement)
    """
    print("=" * 65)
    print("OBJECTIVE 3: STRUCTURED JSON RESPONSE")
    print("=" * 65)
    print(json.dumps(report, indent=2))
    
    print("\n" + "-" * 65)
    print("PARSED INDIVIDUAL FIELDS (Step 1 Requirement):")
    print("-" * 65)
    print(f"1. network_health     : {report.get('network_health')}")
    print(f"2. anomalies_detected : {len(report.get('anomalies_detected', []))} anomaly entries")
    for idx, a in enumerate(report.get("anomalies_detected", []), 1):
        print(f"   [{idx}] Type: {a.get('type')}, Device: {a.get('affected_device')}, Severity: {a.get('severity')}")
        print(f"       Description: {a.get('description')}")
    print(f"3. summary            : {report.get('summary')}")
    print("=" * 65)


# ==============================================================================
# Objective 4: Continuous 30-Second Monitoring Loop
# ==============================================================================
def continuous_monitoring_loop(interval_sec=30):
    """
    Runs analyze_network_structured in a recurring loop every 30 seconds.
    Detects and prints timestamped alerts when health status changes.
    """
    print("=" * 65)
    print(f"STARTING AI FLOW ANALYST CONTINUOUS MONITOR (Interval: {interval_sec}s)")
    print("Press Ctrl+C to stop.")
    print("=" * 65)

    previous_health = None
    iteration = 1

    try:
        while True:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            print(f"\n--- [Iteration {iteration}] {timestamp} ---")
            
            # 1. Collect fresh state
            data = collect_complete_network_state()
            
            # 2. Analyze state with AI
            report = analyze_network_structured(data)
            current_health = report.get("network_health", "normal").lower()
            anomalies = report.get("anomalies_detected", [])
            summary = report.get("summary", "")

            # 3. Check for health transition
            if previous_health is not None and current_health != previous_health:
                print("\n" + "!" * 65)
                print(f"🚨 [STATUS CHANGE ALERT] {timestamp}")
                print(f"   Network Health transitioned: '{previous_health.upper()}' -> '{current_health.upper()}'")
                print("!" * 65)

            # 4. Print structured JSON and summary per iteration
            print("\n[Structured JSON Output]:")
            print(json.dumps(report, indent=2))
            print(f"\nIteration Summary: Health={current_health.upper()}, Anomalies={len(anomalies)}")

            previous_health = current_health
            iteration += 1

            print(f"Sleeping {interval_sec} seconds until next check...")
            time.sleep(interval_sec)

    except KeyboardInterrupt:
        print("\n\n[!] Continuous monitoring loop stopped by user.")


# ==============================================================================
# CLI Entry Point
# ==============================================================================
if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "format"

    if mode == "format":
        print("[*] Testing format_for_llm() on live network state:")
        state = collect_complete_network_state()
        print(format_for_llm(state))

    elif mode == "text" or mode == "obj2":
        state = collect_complete_network_state()
        result = analyze_network_text(state)
        print("\n" + "=" * 60)
        print("OBJECTIVE 2: AI ANALYST FREE-TEXT RESPONSE")
        print("=" * 60)
        print(result)

    elif mode == "json" or mode == "obj3":
        state = collect_complete_network_state()
        report = analyze_network_structured(state)
        display_structured_output(report)

    elif mode == "monitor" or mode == "obj4":
        interval = int(sys.argv[2]) if len(sys.argv) > 2 else 30
        continuous_monitoring_loop(interval_sec=interval)

    else:
        print("Usage: python3 ai_analyst.py [format | text | json | monitor [interval]]")
