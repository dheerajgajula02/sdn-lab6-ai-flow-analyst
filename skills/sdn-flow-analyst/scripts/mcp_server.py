#!/usr/bin/env python3
"""
SDN AI Flow Analyst - Model Context Protocol (MCP) Server
=========================================================
Standard GitHub-grade MCP server providing autonomous agents (Claude, Cursor, OpenCode,
Mimov2.6, etc.) with tools to query network telemetry snapshots, choose custom time windows,
and detect anomalies (traffic floods, rogue DROP rules, blackholes) stored in MongoDB.

Can be run via:
  - stdio (for local terminal coding agents / IDEs):
      python3 mcp_server.py
  - SSE / Network HTTP server:
      python3 mcp_server.py --sse --port 8090
"""

import os
import sys
import json
import re
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any
import pymongo
try:
    from mcp.server.fastmcp import FastMCP
except (ImportError, ModuleNotFoundError):
    import importlib
    try:
        _mcpserver = importlib.import_module("mcp.server.mcpserver")
        FastMCP = getattr(_mcpserver, "MCPServer")
    except Exception:
        from mcp.server import FastMCP  # type: ignore

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Default MongoDB Configuration
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.environ.get("MONGO_DB", "sdn_lab6")
MONGO_COLL = os.environ.get("MONGO_COLL", "telemetry")

from prompt_loader import load_prompt

# Initialize FastMCP Server
mcp = FastMCP(
    "SDN-Flow-Analyst",
    instructions=load_prompt("mcp_server_instructions.md")
)


def get_mongo_collection():
    """Returns the MongoDB telemetry collection."""
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=4000)
    return client[MONGO_DB][MONGO_COLL]


def parse_flexible_time(time_str: str) -> Optional[datetime]:
    """
    Parses various time formats:
    - ISO 8601: '2026-10-07T03:00:00Z', '2026-10-07T03:00:00'
    - Date + Time: '2026-10-07 03:00'
    - Time only: '03:00', '3:00', '3am', '03:30:00' (assumes current date in UTC)
    """
    if not time_str:
        return None
    time_str = time_str.strip()

    # Try ISO formats
    for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
        try:
            dt = datetime.strptime(time_str, fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            pass

    # Try 12-hour or 24-hour time-of-day strings (e.g. "3am", "03:00", "03:30")
    today = datetime.now(timezone.utc).date()
    for time_fmt in ("%H:%M:%S", "%H:%M", "%I:%M%p", "%I%p"):
        try:
            parsed_time = datetime.strptime(time_str.upper(), time_fmt).time()
            return datetime.combine(today, parsed_time, tzinfo=timezone.utc)
        except ValueError:
            pass

    return None


def format_snapshot_summary(doc: Dict[str, Any]) -> str:
    """Formats a single telemetry MongoDB document into a concise summary."""
    ts = doc.get("timestamp", "Unknown")
    data = doc.get("data", {})
    switches = data.get("controller_flow_tables", {})
    port_stats = data.get("port_statistics", {})
    active_counts = data.get("active_flow_counts", {})

    lines = [f"--- Snapshot at {ts} ---"]
    for sw, flows in switches.items():
        flow_count = active_counts.get(sw, len(flows))
        lines.append(f"Switch {sw.upper()} (Active Flows: {flow_count}):")
        
        # Check for heavy hitters or anomalies in ports
        sw_ports = port_stats.get(sw, {})
        for pid, pdata in sw_ports.items():
            rx_b = pdata.get("rx_bytes", 0)
            tx_b = pdata.get("tx_bytes", 0)
            if rx_b > 50000 or tx_b > 50000:
                lines.append(f"  [SPIKE] Port {pid}: Rx={rx_b:,} B, Tx={tx_b:,} B (High Traffic!)")

        # Check for DROP rules or high priority
        for f in flows:
            prio = f.get("priority", 0)
            actions = f.get("actions", [])
            match = f.get("match", {})
            pkts = f.get("packet_count", 0)
            if any("drop" in str(a).lower() for a in actions) or prio > 1000:
                match_str = ", ".join(f"{k}={v}" for k, v in match.items())
                act_str = ", ".join(actions) or "DROP"
                lines.append(f"  [ANOMALY RULE] Priority {prio}: Match({match_str}) -> Actions({act_str}) [Packets: {pkts}]")

    return "\n".join(lines)


# ==============================================================================
# MCP Tools Exposed to LLM Agents
# ==============================================================================

@mcp.tool()
def list_available_time_ranges() -> str:
    """
    Lists the earliest and latest available telemetry snapshot timestamps
    stored in the database, along with total count of recorded snapshots.
    Call this first to know what historical time periods are available to query.
    """
    try:
        coll = get_mongo_collection()
        total = coll.count_documents({})
        if total == 0:
            return "No telemetry snapshots found in database. The ingestion pipeline may just be starting."

        earliest = coll.find().sort("created_at", 1).limit(1)
        latest = coll.find().sort("created_at", -1).limit(1)

        e_doc = next(earliest, {})
        l_doc = next(latest, {})

        return json.dumps({
            "total_snapshots": total,
            "earliest_snapshot_utc": e_doc.get("timestamp"),
            "latest_snapshot_utc": l_doc.get("timestamp"),
            "data_retention_ttl": "24 hours"
        }, indent=2)
    except Exception as e:
        return f"Error listing time ranges from MongoDB: {e}"


@mcp.tool()
def get_latest_telemetry() -> str:
    """
    Retrieves the most recent SDN telemetry snapshot from the network.
    Includes active flow counts, per-port Rx/Tx byte and packet counters,
    and switch connection status.
    """
    try:
        coll = get_mongo_collection()
        doc = coll.find_one(sort=[("created_at", -1)])
        if not doc:
            return "No telemetry snapshots available yet."
        return format_snapshot_summary(doc)
    except Exception as e:
        return f"Error querying latest telemetry: {e}"


@mcp.tool()
def query_telemetry_window(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    minutes_ago: Optional[int] = None,
    limit: int = 10
) -> str:
    """
    Queries historical telemetry snapshots within a custom time window.
    The agent can choose its own window based on the user's inquiry (e.g. 'what happened at 3 am?').

    Args:
        start_time: Beginning of window (e.g. '2026-10-07T03:00:00Z', '2026-10-07 03:00', or '03:00').
        end_time: End of window (defaults to start_time + 1 hour or current time).
        minutes_ago: Optional relative lookback in minutes (e.g. 15 for the last 15 minutes).
        limit: Maximum number of snapshots to return (default: 10).
    """
    try:
        coll = get_mongo_collection()
        query = {}

        if minutes_ago is not None:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
            query["created_at"] = {"$gte": cutoff}
        elif start_time:
            dt_start = parse_flexible_time(start_time)
            if not dt_start:
                return f"Could not parse start_time '{start_time}'. Please use 'YYYY-MM-DD HH:MM' or 'HH:MM'."
            
            if end_time:
                dt_end = parse_flexible_time(end_time)
            else:
                dt_end = dt_start + timedelta(hours=1)

            query["created_at"] = {"$gte": dt_start, "$lte": dt_end}

        cursor = coll.find(query).sort("created_at", 1).limit(limit)
        docs = list(cursor)

        if not docs:
            return f"No snapshots found matching the specified window: {query.get('created_at', 'all')}"

        summaries = [format_snapshot_summary(d) for d in docs]
        return f"Found {len(docs)} snapshot(s) in window:\n\n" + "\n\n".join(summaries)
    except Exception as e:
        return f"Error querying telemetry window: {e}"


@mcp.tool()
def detect_anomalies_in_window(
    start_time: Optional[str] = None,
    end_time: Optional[str] = None,
    minutes_ago: Optional[int] = 30
) -> str:
    """
    Automatically analyzes telemetry snapshots across a time window and identifies anomalies:
    1. High-volume traffic floods (iperf / DoS surges in byte counters).
    2. Rogue / unauthorized DROP flow rules blackholing specific hosts or MACs.
    3. Switch disconnections or state transitions.
    """
    try:
        coll = get_mongo_collection()
        query = {}
        if start_time:
            dt_start = parse_flexible_time(start_time)
            if not dt_start:
                return f"Could not parse start_time '{start_time}'. Please use 'YYYY-MM-DD HH:MM' or 'HH:MM'."
            dt_end = parse_flexible_time(end_time) if end_time else dt_start + timedelta(hours=1)
            query["created_at"] = {"$gte": dt_start, "$lte": dt_end}
        elif minutes_ago:
            cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes_ago)
            query["created_at"] = {"$gte": cutoff}

        docs = list(coll.find(query).sort("created_at", 1))
        if not docs:
            return "No snapshots found in specified range to analyze."

        anomalies_found = []

        for doc in docs:
            ts = doc.get("timestamp")
            data = doc.get("data", {})
            switches = data.get("controller_flow_tables", {})
            ports = data.get("port_statistics", {})

            # 1. Check for rogue drop rules
            for sw, flows in switches.items():
                for f in flows:
                    prio = f.get("priority", 0)
                    actions = f.get("actions", [])
                    match = f.get("match", {})
                    if any("drop" in str(a).lower() for a in actions) or prio >= 10000:
                        anomalies_found.append({
                            "timestamp": ts,
                            "type": "Rogue DROP Rule",
                            "switch": sw,
                            "severity": "high",
                            "details": f"Priority {prio} rule matching {match} with actions {actions}"
                        })

            # 2. Check for port floods (over 1 MB)
            for sw, pmap in ports.items():
                for pid, pdata in pmap.items():
                    rx_bytes = pdata.get("rx_bytes", 0)
                    tx_bytes = pdata.get("tx_bytes", 0)
                    if rx_bytes > 1_000_000 or tx_bytes > 1_000_000:
                        anomalies_found.append({
                            "timestamp": ts,
                            "type": "Traffic Flood / DoS",
                            "switch": sw,
                            "port": pid,
                            "severity": "high",
                            "details": f"Port {pid} exceeded 1 MB (Rx: {rx_bytes:,} B, Tx: {tx_bytes:,} B)"
                        })

        if not anomalies_found:
            return f"Analysis complete for {len(docs)} snapshots: No anomalies detected. Network health is NORMAL."

        return json.dumps({
            "status": "ANOMALIES_DETECTED",
            "total_snapshots_analyzed": len(docs),
            "anomaly_events_count": len(anomalies_found),
            "anomalies": anomalies_found
        }, indent=2)
    except Exception as e:
        return f"Error detecting anomalies: {e}"


def create_app():
    """Returns the Starlette SSE application configured for public network access."""
    import inspect
    sse_func = getattr(mcp, "sse_app")
    params = inspect.signature(sse_func).parameters

    if "transport_security" in params:
        try:
            import importlib
            ts_mod = importlib.import_module("mcp.server.transport_security")
            TS = getattr(ts_mod, "TransportSecuritySettings")
            sec = TS(
                enable_dns_rebinding_protection=False,
                allowed_hosts=["*"],
                allowed_origins=["*"]
            )
            return sse_func(transport_security=sec)
        except Exception:
            pass

    if "host" in params:
        return sse_func(host="0.0.0.0")

    return sse_func()


# ==============================================================================
# Main Entry Point
# ==============================================================================
if __name__ == "__main__":
    if "--sse" in sys.argv:
        port = 8090
        if "--port" in sys.argv:
            idx = sys.argv.index("--port")
            if idx + 1 < len(sys.argv):
                port = int(sys.argv[idx + 1])
        print(f"[*] Starting SDN Flow Analyst MCP Server on SSE (http://0.0.0.0:{port}/sse)...")
        import uvicorn
        uvicorn.run(create_app(), host="0.0.0.0", port=port)
    else:
        # Default: stdio transport for local coding agents / Claude Desktop / Opencode
        mcp.run()
