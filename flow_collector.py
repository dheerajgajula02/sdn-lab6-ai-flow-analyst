#!/usr/bin/env python3
"""
CSCI 5280 - Lab 6: AI Flow Analyst
Objective 1: Flow and Network Data Collector

Collects:
1. Flow table entries via Ryu REST API (/stats/flow/<dpid>)
2. Per-port packet and byte counters via ovs-ofctl dump-ports
3. Switch connection status via ovs-vsctl show
4. Active flow counts per switch
"""

import sys
import os
import json
import subprocess
import re
from datetime import datetime
import requests

def _get_default_controller_ip():
    # If ovs-ofctl is present locally, we are running on the Mininet VM
    if subprocess.call(["which", "ovs-ofctl"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0:
        return "10.224.78.132"
    # Running remotely on laptop: use Tailscale IP
    return "100.110.3.67"

CONTROLLER_IP = os.environ.get("CONTROLLER_IP", _get_default_controller_ip())
CONTROLLER_PORT = os.environ.get("CONTROLLER_PORT", "8080")
CONTROLLER_URL = "http://{}:{}".format(CONTROLLER_IP, CONTROLLER_PORT)

MININET_HOST = os.environ.get("MININET_HOST", "100.73.87.23")
MININET_USER = os.environ.get("MININET_USER", "mininet")
MININET_PASS = os.environ.get("MININET_PASS", "mininet")

SWITCHES = ["s1", "s2"]


def _run_cmd(cmd_list):
    """
    Run command locally if ovs-ofctl is present, otherwise SSH to Mininet VM.
    Compatible with Python 3.4+.
    """
    is_local_ovs = subprocess.call(["which", "ovs-ofctl"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
    if is_local_ovs:
        # We are on the Mininet VM
        full_cmd = ["sudo", "-S"] + cmd_list
        proc = subprocess.Popen(full_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        stdout, _ = proc.communicate(MININET_PASS + "\n")
        lines = [l for l in stdout.splitlines() if not l.startswith("[sudo]")]
        return "\n".join(lines)
    else:
        # We are running remotely (e.g., from host laptop)
        cmd_str = "echo {} | sudo -S {}".format(MININET_PASS, " ".join(cmd_list))
        ssh_cmd = [
            "sshpass", "-p", MININET_PASS,
            "ssh", "-o", "StrictHostKeyChecking=no",
            "{}@{}".format(MININET_USER, MININET_HOST),
            cmd_str
        ]
        proc = subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        stdout, _ = proc.communicate()
        # Filter out [sudo] prompt line if present
        lines = [l for l in stdout.splitlines() if not l.startswith("[sudo]")]
        return "\n".join(lines)


# ==============================================================================
# Objective 1, Step 2: collect_flow_data() via Controller REST API
# ==============================================================================
def collect_flow_data(controller_url=CONTROLLER_URL):
    """
    Queries Ryu REST API and retrieves current flow table entries for all switches.
    Returns a Python dictionary: { switch_dpid: [flow_entries] }
    """
    switches_url = "{}/stats/switches".format(controller_url)
    resp = requests.get(switches_url, timeout=5)
    resp.raise_for_status()
    dpids = resp.json()

    flow_data = {}
    for dpid in dpids:
        flow_url = "{}/stats/flow/{}".format(controller_url, dpid)
        flow_resp = requests.get(flow_url, timeout=5)
        flow_resp.raise_for_status()
        flows = flow_resp.json()
        # Ryu returns { "<dpid>": [flows...] }
        dpid_str = str(dpid)
        flow_data["s{}".format(dpid)] = flows.get(dpid_str, [])

    return flow_data


# ==============================================================================
# Objective 1, Step 3: OVS Subprocess Metrics & Consolidated State
# ==============================================================================
def parse_port_stats(raw_output):
    """
    Parses 'ovs-ofctl dump-ports' output into a clean dictionary of port stats.
    """
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
    """
    Parses 'ovs-vsctl show' output into a structured dictionary of bridges and their status.
    """
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


def collect_ovs_data(switches=SWITCHES):
    """
    Retrieves OVS data via subprocess calls:
    - Per-port packet and byte counters (ovs-ofctl dump-ports)
    - Switch connection status (ovs-vsctl show)
    - Active flow count per switch
    """
    port_stats = {}
    active_flow_counts = {}

    for sw in switches:
        # Per-port packet and byte counters
        ports_raw = _run_cmd(["ovs-ofctl", "-O", "OpenFlow13", "dump-ports", sw])
        port_stats[sw] = parse_port_stats(ports_raw)

        # Active flow count per switch (counting flow rules excluding OF header)
        flows_raw = _run_cmd(["ovs-ofctl", "-O", "OpenFlow13", "dump-flows", sw])
        flow_lines = [l for l in flows_raw.splitlines() if "cookie=" in l]
        active_flow_counts[sw] = len(flow_lines)

    # Switch connection status parsed into structured dictionary
    vsctl_raw = _run_cmd(["ovs-vsctl", "show"]).strip()
    vsctl_show = parse_vsctl_show(vsctl_raw)

    return {
        "port_statistics": port_stats,
        "active_flow_counts": active_flow_counts,
        "switch_connection_status": vsctl_show,
    }


def collect_complete_network_state():
    """
    Consolidates controller REST flow tables and OVS subprocess data into
    a single structured dictionary for the AI Analyst.
    """
    flow_tables = collect_flow_data()
    ovs_data = collect_ovs_data()

    complete_state = {
        "timestamp": datetime.now().isoformat(),
        "controller_flow_tables": flow_tables,
        "port_statistics": ovs_data["port_statistics"],
        "active_flow_counts": ovs_data["active_flow_counts"],
        "switch_connection_status": ovs_data["switch_connection_status"],
    }
    return complete_state


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"

    if mode == "step2" or mode == "flows":
        print("=" * 70)
        print("Objective 1 - Step 2: Flow Data via Controller REST API")
        print("=" * 70)
        flows = collect_flow_data()
        print(json.dumps(flows, indent=2))

    elif mode == "step3" or mode == "ovs":
        print("=" * 70)
        print("Objective 1 - Step 3: OVS Subprocess Data Collection")
        print("=" * 70)
        ovs = collect_ovs_data()
        print(json.dumps(ovs, indent=2))

    else:
        print("=" * 70)
        print("Objective 1 - Complete Structured Network State")
        print("=" * 70)
        state = collect_complete_network_state()
        print(json.dumps(state, indent=2))
