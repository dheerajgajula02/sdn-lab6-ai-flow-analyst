# SDN Flow Analyst MCP Server Instructions

The `sdn-flow-analyst` MCP server provides real-time and historical OpenFlow telemetry inspection across SDN switches (`s1`, `s2`) and connected hosts (`h1` - `h8`). Telemetry is sampled once per minute and stored with a 24-hour TTL in MongoDB.

## Available Tools

1. **`list_available_time_ranges`**:
   - Use first to inspect available snapshot timestamps and total count.
   - Tells you the earliest and latest UTC timestamps recorded.

2. **`get_latest_telemetry`**:
   - Returns the most recent snapshot containing active flow counts, port statistics (Rx/Tx bytes), and flow entries.

3. **`query_telemetry_window`**:
   - Query historical snapshots by time window.
   - Accepts `start_time` (e.g. `'03:00'`, `'2026-10-07T03:00:00Z'`), `end_time`, or `minutes_ago` (e.g. `15`).
   - Slices snapshots to answer questions like "What happened at 3 AM?".

4. **`detect_anomalies_in_window`**:
   - Automated heuristic scanner across a specified time window.
   - Detects traffic floods (surge > 1 MB Rx/Tx) and rogue DROP flow rules (priority >= 10000 or DROP actions).

## Typical Investigation Workflow

1. Call `list_available_time_ranges` to identify the boundary of recorded telemetry.
2. If the user asks about an event or incident (e.g. "What happened at 3 AM?" or "Is there an anomaly right now?"):
   - For historical incidents: Call `query_telemetry_window(start_time="03:00")` or `detect_anomalies_in_window(start_time="03:00")`.
   - For live status: Call `get_latest_telemetry` or `detect_anomalies_in_window(minutes_ago=15)`.
3. If an anomaly is found:
   - Identify switch ID (`s1` or `s2`), affected ports, and matching headers (MAC, IP, priority).
   - Classify as **Traffic Flood / DoS** or **Rogue Flow Rule / Blackhole**.
   - Formulate recommended mitigation (e.g. flow rule removal via REST or host traffic rate limiting).
