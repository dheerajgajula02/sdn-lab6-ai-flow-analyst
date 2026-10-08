---
name: sdn-flow-analyst
description: Autonomous SDN Flow Analyst skill for inspecting OpenFlow telemetry, querying historical snapshot windows in MongoDB, and detecting network anomalies (traffic floods, rogue DROP rules, blackholes).
---

# SDN Flow Analyst Skill

This skill equips autonomous AI agents (OpenCode, Mimov2.6, Cursor, Antigravity, Claude Code) with tools, scripts, and workflows to monitor, query, and diagnose OpenFlow Software-Defined Networks (SDN).

---

## 1. Architecture & Telemetry Pipeline

```
+--------------------------------------------------------------+
| Mininet Topology (100.73.87.23 / 10.224.76.126)              |
|   Switches: s1 (dpid: 1), s2 (dpid: 2)                       |
|   Hosts: h1-h4 (on s1), h5-h8 (on s2)                        |
+------------------------------+-------------------------------+
                               | OpenFlow 1.3 (Port 6633)
+------------------------------v-------------------------------+
| Ryu Controller (100.110.3.67 / 10.224.78.132)                |
|   Apps: simple_switch_13, ofctl_rest (Port 8080)             |
+------------------------------+-------------------------------+
                               | REST Ingestion (Every 1 min)
+------------------------------v-------------------------------+
| Jenkins Ingestion Pipeline (10.0.0.10:8080)                   |
|   Job: lab6-sdn-telemetry (pull_and_push_mongo.py)           |
+------------------------------+-------------------------------+
                               | Insert with 24-hr TTL
+------------------------------v-------------------------------+
| MongoDB Database (100.111.97.101:27017 / 10.0.0.146:27017)   |
|   DB: sdn_lab6, Collection: telemetry (TTL Index: 86400s)     |
+------------------------------+-------------------------------+
                               | SSE / stdio Protocol
+------------------------------v-------------------------------+
| MCP Server (10.0.0.174:8090/sse or local stdio)             |
|   Exposes: list_available_time_ranges, query_telemetry_window|
|            get_latest_telemetry, detect_anomalies_in_window  |
+--------------------------------------------------------------+
```

---

## 2. When to Use This Skill

Activate this skill whenever:
- The user asks about SDN network performance, switch port counters, or flow tables.
- The user asks about an incident or event at a specific time (e.g., *"What happened at 3 AM?"*, *"Why did traffic drop at 14:30?"*).
- Investigating potential anomalies:
  - **Traffic Floods / DoS**: Massive spike in per-port Rx/Tx byte counts (e.g., UDP iperf storm).
  - **Rogue DROP Rules / Blackholes**: High-priority flow rules (priority >= 10000) with empty actions or DROP.
- Verifying controller connectivity or running automated network audits.

---

## 3. Tool Usage & Decision Guide

Agents should interact via either **MCP Tools** (preferred) or the **CLI Scripts**:

### MCP Tools Available
1. `list_available_time_ranges`:
   - Always run first if you need to know how far back telemetry is stored or verify that the pipeline is active.
2. `get_latest_telemetry`:
   - Returns real-time snapshot: active flow counts, switch connection status, port counters.
3. `query_telemetry_window`:
   - **Time window queries**: When the user specifies a time like "3 am" or "10 minutes ago", pass:
     - `start_time="03:00"` or `start_time="2026-10-07 03:00"`
     - Or `minutes_ago=15` for recent lookbacks.
   - Inspects the exact state of flow tables and port traffic during that window.
4. `detect_anomalies_in_window`:
   - Automated heuristic scanner that filters snapshots for traffic floods (> 1MB byte delta) and rogue DROP rules.

---

## 4. Anomaly Diagnosis Playbook

### Scenario A: Traffic Flood / Denial of Service
- **Symptom**: Port Rx/Tx bytes jump from tens of kilobytes to tens of megabytes.
- **Root Cause**: Host transmitting flood traffic (e.g., `iperf -u -b 100M`).
- **Remediation**:
  1. Identify sending switch and port.
  2. Map port to host (e.g., switch `s1` port 1 = `h1`, port 2 = `h2`, port 3 = `h3`, port 4 = `h4`).
  3. Deploy OpenFlow meter or rate-limiting rule via Ryu REST API.

### Scenario B: Rogue DROP Rule / Host Isolation
- **Symptom**: Host cannot ping gateway or other hosts (`Destination Host Unreachable` or 100% packet loss).
- **Root Cause**: Flow rule with priority > 1000 (often 65535 or 10000) matching specific MAC/IP with `actions: []`.
- **Remediation**:
  1. Identify switch DPID (`1` for `s1`, `2` for `s2`).
  2. Send OpenFlow `delete_strict` REST call to `http://<controller-ip>:8080/stats/flowentry/delete_strict`.

---

## 5. Local Scripts & Execution

If MCP is not active or you need direct execution, use the scripts in `scripts/`:

```bash
# 1. Run Autonomous ReAct Terminal Agent
python3 scripts/terminal_agent.py

# 2. Query MongoDB snapshots directly
python3 -c "
import os, pymongo
client = pymongo.MongoClient(os.environ.get('MONGO_URI', 'mongodb://localhost:27017'))
doc = client['sdn_lab6']['telemetry'].find_one(sort=[('created_at', -1)])
print('Latest snapshot:', doc['timestamp'])
"

# 3. Simulate or clear anomalies
python3 scripts/anomalies.py flood    # Inject UDP flood
python3 scripts/anomalies.py drop     # Inject rogue DROP rule
python3 scripts/anomalies.py clear    # Restore clean state
```

---

## 6. Resources & References

- [Architecture Reference](references/architecture.md)
- [OpenFlow 1.3 Ryu REST API Reference](references/openflow_cheatsheet.md)
- [Telemetry Collector](scripts/flow_collector.py)
- [AI Analyst Engine](scripts/ai_analyst.py)
- [MCP Server](scripts/mcp_server.py)
