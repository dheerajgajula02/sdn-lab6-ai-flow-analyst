# CSCI 5280 - Lab 6: AI Flow Analyst

An autonomous, LLM-powered Software-Defined Network (SDN) telemetry analyzer and real-time monitoring engine built on OpenFlow 1.3, Ryu Controller, Open vSwitch (OVS), MongoDB, and Model Context Protocol (MCP).

---

## Architecture Overview

```
                      +-----------------------------+
                      |     Ryu SDN Controller      |
                      | (simple_switch_13, ofctl_rest)|
                      +--------------+--------------+
                                     | OpenFlow 1.3 / REST API (:8080)
                                     v
+------------------+         +-------------------------------+
|  Mininet Network | <-----> |       flow_collector.py       |
| (s1, s2, h1..h8) |         | (REST + OVS subprocess calls) |
+------------------+         +---------------+---------------+
         |                                   |
         | Raw Packets                       v Structured JSON State
         v                           +-------------------------------+
+------------------+                 |         ai_analyst.py         |
| anomoly_injection|                 | - format_for_llm()            |
| - start_flood.py |                 | - analyze_network_text()      |
| - install_drop...|                 | - analyze_network_structured()|
+------------------+                 | - continuous_monitoring_loop()|
                                     +---------------+---------------+
                                                     |
                                                     v
                                     +-------------------------------+
                                     |    OpenAI-Compatible LLM     |
                                     |  (Xiaomi MiMo 2.6 Flash /     |
                                     |   GPT-4o-mini / DeepSeek)     |
                                     +-------------------------------+
```

---

## Project Structure

```
├── .env.example             # Environment variable template with placeholders
├── .gitignore               # Git ignore rules protecting .env and bytecode
├── README.md                # Project documentation and usage guide
├── requirements.txt         # Python dependencies
├── topo_lab6.py             # Mininet topology (2 switches, 8 hosts, OF1.3)
├── flow_collector.py        # Objective 1: REST & OVS metrics collector
├── ai_analyst.py            # Objectives 2-4: Free-text, JSON, and continuous monitoring
├── prompt_loader.py         # Modular prompt loading utility
├── prompts/                 # Decoupled system, user, and schema prompt templates
├── anomoly_injection/       # Objective 1, Step 4: Standalone anomaly injection scripts
│   ├── start_flood.py       # Starts 50 Mbps UDP flood (h1 -> h4)
│   ├── stop_flood.py        # Terminates traffic flood
│   ├── install_drop_rule.py # Installs high-priority DROP rule on s1 (h2 blackhole)
│   ├── remove_drop_rule.py  # Deletes rogue DROP rule
│   └── check_status.py      # Verifies ground-truth status of both conditions
├── mcp_server.py            # Model Context Protocol (MCP) server for agents
├── terminal_agent.py        # Autonomous ReAct agentic CLI loop over MCP tools
├── pull_and_push_mongo.py   # 24-hour TTL MongoDB telemetry ingestion script
└── Jenkinsfile              # Recurring telemetry ingestion pipeline definition
```

---

## Setup & Configuration

1. **Clone the repository:**
   ```bash
   git clone https://github.com/dheerajgajula02/sdn-lab6-ai-flow-analyst.git
   cd sdn-lab6-ai-flow-analyst
   ```

2. **Install Python dependencies:**
   ```bash
   pip3 install -r requirements.txt
   ```

3. **Configure Environment Variables:**
   Copy `.env.example` to `.env` and fill in your LLM and network credentials:
   ```bash
   cp .env.example .env
   ```

---

## Usage Guide by Objective

### Objective 1: Data Collection & Anomalies
- **Collect Ryu REST flows:**
  ```bash
  python3 flow_collector.py flows
  ```
- **Collect complete structured network state (REST + OVS):**
  ```bash
  python3 flow_collector.py
  ```
- **Inject Anomaly 1 (Traffic Flood):**
  ```bash
  python3 anomoly_injection/start_flood.py
  ```
- **Inject Anomaly 2 (Rogue DROP Rule):**
  ```bash
  python3 anomoly_injection/install_drop_rule.py
  ```
- **Check anomaly status:**
  ```bash
  python3 anomoly_injection/check_status.py
  ```

### Objective 2: Free-Text AI Analyst
- **Test LLM prompt formatting:**
  ```bash
  python3 ai_analyst.py format
  ```
- **Run free-text expert network engineering analysis:**
  ```bash
  python3 ai_analyst.py text
  ```

### Objective 3: Structured Output
- **Run structured JSON analysis (with automatic 1-retry defensive parsing):**
  ```bash
  python3 ai_analyst.py json
  ```

### Objective 4: Continuous Monitoring Loop
- **Start the real-time continuous monitoring loop (configurable interval):**
  ```bash
  python3 ai_analyst.py monitor 30
  ```

### Advanced: Autonomous ReAct Terminal Agent (MCP)
- **Start the autonomous terminal agent loop:**
  ```bash
  python3 terminal_agent.py "What happened to switch s1 traffic in the last 15 minutes?"
  ```
