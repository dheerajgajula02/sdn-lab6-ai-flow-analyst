# SDN Flow Analyst Architecture & Network Topology

## 1. Network Topology (Mininet)

- **Host**: `mininet-ofm` (`100.73.87.23` / LAN `10.224.76.126`)
- **Controller Target**: `10.224.78.132:6633` (OpenFlow 1.3)
- **Switches**:
  - `s1` (DPID `0000000000000001`): Connects `h1`, `h2`, `h3`, `h4` and uplink to `s2`
  - `s2` (DPID `0000000000000002`): Connects `h5`, `h6`, `h7`, `h8` and uplink to `s1`
- **Hosts**:
  - Subnet: `10.0.0.0/24`
  - IP mappings: `h1` = `10.0.0.1` ... `h8` = `10.0.0.8`
  - MAC mappings: `00:00:00:00:00:01` ... `00:00:00:00:00:08`

## 2. SDN Controller (Ryu)

- **Host**: `sdn-controllers` (`100.110.3.67` / LAN `10.224.78.132`)
- **OpenFlow Port**: `6633` (OF 1.3)
- **REST Port**: `8080`
- **Ryu Apps**:
  - `ryu.app.simple_switch_13`: MAC learning and flow table installation
  - `ryu.app.ofctl_rest`: REST interface for flow & port statistics

## 3. Telemetry Storage & Retention (MongoDB)

- **Auth**: Configured via environment variables (`MONGO_URI`) with `authSource=admin`
- **Database**: `sdn_lab6`
- **Collection**: `telemetry`
- **Retention**: Document TTL index `expireAfterSeconds: 86400` (24 hours) on `created_at` field

## 4. Ingestion Engine (Jenkins)

- **Host**: `boulderserver` (`10.0.0.10:8080`)
- **Job**: `lab6-sdn-telemetry`
- **Trigger**: Cron `* * * * *` (every minute)
- **Script**: `pull_and_push_mongo.py`

## 5. MCP Server (SSE & Stdio)

- **Host**: `debian-adb` (`10.0.0.174:8090/sse`)
- **Service**: `mcp-sdn.service`
- **Tools**:
  - `list_available_time_ranges`
  - `get_latest_telemetry`
  - `query_telemetry_window`
  - `detect_anomalies_in_window`
