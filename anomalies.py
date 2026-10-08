#!/usr/bin/env python3
"""
CSCI 5280 - Lab 6: AI Flow Analyst
Objective 1, Step 4: Anomaly Injector & Cleaner

Anomalies:
1. Traffic Flood: High-volume UDP flood from h1 to h4 using iperf.
2. Suspicious Flow: High-priority DROP rule installed on s1 for host h2.
"""

import sys
import subprocess
import os

MININET_HOST = os.environ.get("MININET_HOST", "100.73.87.23")
MININET_USER = os.environ.get("MININET_USER", "mininet")
MININET_PASS = os.environ.get("MININET_PASS", "mininet")


def _run_in_mininet(cmd):
    """
    Sends a command to the Mininet CLI running in tmux session 'mininet_lab6',
    or runs bash command via SSH if needed.
    """
    is_local = subprocess.call(["which", "ovs-ofctl"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
    if is_local:
        tmux_cmd = ["sudo", "-S", "tmux", "send-keys", "-t", "mininet_lab6", cmd, "C-m"]
        proc = subprocess.Popen(tmux_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        proc.communicate(MININET_PASS + "\n")
    else:
        cmd_str = "echo {} | sudo -S tmux send-keys -t mininet_lab6 '{}' C-m".format(MININET_PASS, cmd)
        ssh_cmd = [
            "sshpass", "-p", MININET_PASS,
            "ssh", "-o", "StrictHostKeyChecking=no",
            "{}@{}".format(MININET_USER, MININET_HOST),
            cmd_str
        ]
        subprocess.run(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def _run_ovs(cmd_list):
    """Executes ovs command locally or via SSH."""
    is_local = subprocess.call(["which", "ovs-ofctl"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL) == 0
    if is_local:
        full_cmd = ["sudo", "-S"] + cmd_list
        proc = subprocess.Popen(full_cmd, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        out, _ = proc.communicate(MININET_PASS + "\n")
        return out
    else:
        cmd_str = "echo {} | sudo -S {}".format(MININET_PASS, " ".join(cmd_list))
        ssh_cmd = [
            "sshpass", "-p", MININET_PASS,
            "ssh", "-o", "StrictHostKeyChecking=no",
            "{}@{}".format(MININET_USER, MININET_HOST),
            cmd_str
        ]
        proc = subprocess.Popen(ssh_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, universal_newlines=True)
        out, _ = proc.communicate()
        lines = [l for l in out.splitlines() if not l.startswith("[sudo]")]
        return "\n".join(lines)


def inject_flood():
    print("[*] Starting iperf UDP traffic flood: h1 -> h4 (50 Mbps)...")
    _run_in_mininet("h4 pkill -9 iperf")
    _run_in_mininet("h1 pkill -9 iperf")
    _run_in_mininet("h4 iperf -s -u -p 5001 &")
    _run_in_mininet("h1 iperf -c 10.0.0.4 -u -b 50M -t 3600 &")
    print("[+] Traffic flood started.")


def stop_flood():
    print("[*] Stopping iperf traffic flood...")
    _run_in_mininet("h1 pkill -9 iperf")
    _run_in_mininet("h4 pkill -9 iperf")
    print("[+] Traffic flood stopped.")


def inject_suspicious_flow():
    print("[*] Installing suspicious DROP flow entry on s1 (dropping traffic from h2 00:00:00:00:00:02)...")
    rule = "priority=50000,dl_src=00:00:00:00:00:02,actions=drop"
    _run_ovs(["ovs-ofctl", "-O", "OpenFlow13", "add-flow", "s1", rule])
    print("[+] Suspicious flow entry installed.")


def remove_suspicious_flow():
    print("[*] Removing suspicious flow entry on s1...")
    _run_ovs(["ovs-ofctl", "-O", "OpenFlow13", "del-flows", "s1", "dl_src=00:00:00:00:00:02"])
    print("[+] Suspicious flow removed.")


def show_status():
    print("=" * 60)
    print("CURRENT ANOMALIES STATUS")
    print("=" * 60)
    # Check iperf processes
    out = _run_ovs(["ps", "aux"])
    iperf_lines = [l for l in out.splitlines() if "iperf" in l and "grep" not in l]
    print("\n[1] Traffic Flood (iperf):")
    if iperf_lines:
        for l in iperf_lines:
            print("    " + l)
    else:
        print("    No active iperf flood processes found.")

    # Check suspicious flow
    flows = _run_ovs(["ovs-ofctl", "-O", "OpenFlow13", "dump-flows", "s1"])
    suspicious = [l for l in flows.splitlines() if "50000" in l or "drop" in l]
    print("\n[2] Suspicious Flow Entries on s1:")
    if suspicious:
        for l in suspicious:
            print("    " + l)
    else:
        print("    No suspicious flow rules found on s1.")


if __name__ == "__main__":
    action = sys.argv[1] if len(sys.argv) > 1 else "status"

    if action == "start" or action == "inject":
        inject_flood()
        inject_suspicious_flow()
        show_status()
    elif action == "stop" or action == "clear":
        stop_flood()
        remove_suspicious_flow()
        show_status()
    elif action == "flood":
        inject_flood()
        show_status()
    elif action == "flow":
        inject_suspicious_flow()
        show_status()
    else:
        show_status()
