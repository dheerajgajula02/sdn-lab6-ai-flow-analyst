#!/usr/bin/env python3
"""
CSCI 5280 - Lab 6: Telemetry Pipeline
Pulls live OpenFlow telemetry from SDN Controller and Mininet,
then writes to MongoDB with an automatic 24-hour (1-day) TTL index.
"""

import os
import sys
import json
import re
import subprocess
from datetime import datetime, timezone
import requests
import pymongo

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB = os.environ.get("MONGO_DB", "sdn_lab6")
MONGO_COLL = os.environ.get("MONGO_COLL", "telemetry")

CONTROLLER_URL = os.environ.get("CONTROLLER_URL", "http://100.110.3.67:8080")
MININET_HOST = os.environ.get("MININET_HOST", "100.73.87.23")
MININET_USER = os.environ.get("MININET_USER", "mininet")
MININET_PASS = os.environ.get("MININET_PASS", "mininet")

SWITCHES = ["s1", "s2"]


def run_mininet_cmd(cmd_list):
    """Executes a command on the Mininet VM over SSH or locally if ovs-ofctl is present."""
    if subprocess.call(["which", "ovs-ofctl"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
        full_cmd = ["sudo", "-S"] + cmd_list
        proc = subprocess.Popen(full_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        stdout, _ = proc.communicate(MININET_PASS + "\n")
        lines = [l for l in stdout.splitlines() if not l.startswith("[sudo]")]
        return "\n".join(lines)
    else:
        cmd_str = "echo {} | sudo -S {}".format(MININET_PASS, " ".join(cmd_list))
        ssh_cmd = [
            "sshpass", "-p", MININET_PASS,
            "ssh", "-o", "StrictHostKeyChecking=no", "-o", "ConnectTimeout=5",
            "{}@{}".format(MININET_USER, MININET_HOST),
            cmd_str
        ]
        proc = subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        stdout, _ = proc.communicate()
        lines = [l for l in stdout.splitlines() if not l.startswith("[sudo]")]
        return "\n".join(lines)


def collect_flow_data():
    """Queries Ryu REST API and retrieves current flow table entries."""
    switches_url = f"{CONTROLLER_URL}/stats/switches"
    resp = requests.get(switches_url, timeout=5)
    resp.raise_for_status()
    dpids = resp.json()

    flow_data = {}
    for dpid in dpids:
        flow_url = f"{CONTROLLER_URL}/stats/flow/{dpid}"
        flow_resp = requests.get(flow_url, timeout=5)
        flow_resp.raise_for_status()
        flows = flow_resp.json()
        flow_data[f"s{dpid}"] = flows.get(str(dpid), [])
    return flow_data


def parse_port_stats(raw_output):
    """Parses ovs-ofctl dump-ports into a structured dictionary."""
    ports = {}
    current_port = None
    for line in raw_output.splitlines():
        line = line.strip()
        port_match = re.match(r"port\s+(\w+):\s+rx pkts=(\d+),\s+bytes=(\d+),\s+drop=(\d+),\s+errs=(\d+)", line)
        if port_match:
            current_port = port_match.group(1)
            ports[current_port] = {
                "rx_pkts": int(port_match.group(2)),
                "rx_bytes": int(port_match.group(3)),
                "rx_drop": int(port_match.group(4)),
                "rx_errs": int(port_match.group(5)),
            }
            continue
        tx_match = re.match(r"tx pkts=(\d+),\s+bytes=(\d+),\s+drop=(\d+),\s+errs=(\d+)", line)
        if tx_match and current_port:
            ports[current_port].update({
                "tx_pkts": int(tx_match.group(1)),
                "tx_bytes": int(tx_match.group(2)),
                "tx_drop": int(tx_match.group(3)),
                "tx_errs": int(tx_match.group(4)),
            })
    return ports


def parse_vsctl_show(raw_output):
    """Parses 'ovs-vsctl show' output into a structured dictionary."""
    bridges = {}
    current_bridge = None
    for line in raw_output.splitlines():
        line = line.strip()
        br_match = re.match(r'Bridge\s+"?(\w+)"?', line)
        if br_match:
            current_bridge = br_match.group(1)
            bridges[current_bridge] = {
                "controllers": [],
                "is_connected": False,
                "fail_mode": "standalone",
                "ports": []
            }
            continue
        if not current_bridge:
            continue
        ctrl_match = re.match(r'Controller\s+"([^"]+)"', line)
        if ctrl_match:
            bridges[current_bridge]["controllers"].append(ctrl_match.group(1))
        elif "is_connected: true" in line:
            bridges[current_bridge]["is_connected"] = True
        elif line.startswith("fail_mode:"):
            bridges[current_bridge]["fail_mode"] = line.split(":", 1)[1].strip()
        port_match = re.match(r'Port\s+"?([^"]+)"?', line)
        if port_match:
            bridges[current_bridge]["ports"].append(port_match.group(1))
    return bridges


def collect_ovs_data():
    """Retrieves port statistics and active flow counts via ovs-ofctl and ovs-vsctl."""
    port_stats = {}
    active_flow_counts = {}

    for sw in SWITCHES:
        ports_raw = run_mininet_cmd(["ovs-ofctl", "-O", "OpenFlow13", "dump-ports", sw])
        port_stats[sw] = parse_port_stats(ports_raw)

        flows_raw = run_mininet_cmd(["ovs-ofctl", "-O", "OpenFlow13", "dump-flows", sw])
        flow_lines = [l for l in flows_raw.splitlines() if "cookie=" in l]
        active_flow_counts[sw] = len(flow_lines)

    vsctl_raw = run_mininet_cmd(["ovs-vsctl", "show"]).strip()
    vsctl_show = parse_vsctl_show(vsctl_raw)

    return {
        "port_statistics": port_stats,
        "active_flow_counts": active_flow_counts,
        "switch_connection_status": vsctl_show,
    }


def pull_telemetry():
    """Gathers the complete network telemetry dictionary."""
    flow_tables = collect_flow_data()
    ovs_data = collect_ovs_data()

    now = datetime.now(timezone.utc)
    return {
        "timestamp": now.isoformat(),
        "controller_flow_tables": flow_tables,
        "port_statistics": ovs_data["port_statistics"],
        "active_flow_counts": ovs_data["active_flow_counts"],
        "switch_connection_status": ovs_data["switch_connection_status"],
    }


def push_to_mongodb(telemetry_data):
    """
    Inserts telemetry into MongoDB with a 24-hour TTL index on 'created_at'.
    """
    client = pymongo.MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client[MONGO_DB]
    coll = db[MONGO_COLL]

    # Ensure TTL index is set to 86400 seconds (24 hours = 1 day)
    coll.create_index([("created_at", pymongo.ASCENDING)], expireAfterSeconds=86400)

    now = datetime.now(timezone.utc)
    doc = {
        "created_at": now,  # BSON Date used by MongoDB for TTL expiration
        "timestamp": now.isoformat(),
        "data": telemetry_data
    }

    result = coll.insert_one(doc)
    doc_count = coll.count_documents({})
    return result.inserted_id, doc_count


def main():
    print("=" * 60)
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Starting SDN Telemetry Pull & MongoDB Push")
    print("=" * 60)

    try:
        print("[*] Pulling telemetry from SDN Controller & Mininet...")
        data = pull_telemetry()
        switches = list(data.get("controller_flow_tables", {}).keys())
        print(f"[+] Successfully collected telemetry for switches: {switches}")

        print(f"[*] Connecting to MongoDB at {MONGO_URI.split('@')[-1]}...")
        doc_id, total_docs = push_to_mongodb(data)
        print(f"[SUCCESS] Inserted document ID: {doc_id}")
        print(f"[+] Total documents in '{MONGO_DB}.{MONGO_COLL}': {total_docs} (TTL: 24 hours)")
        print("=" * 60)

    except Exception as e:
        print(f"[ERROR] Failed to pull/push telemetry: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
