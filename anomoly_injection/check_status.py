#!/usr/bin/env python3
"""
CSCI 5280 - Lab 6: Objective 1, Step 4
Inspect Active Anomalies Status.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import flow_collector

def check_status():
    print("=" * 65)
    print("           NETWORK ANOMALY INJECTION STATUS")
    print("=" * 65)
    
    # 1. Check iperf traffic flood (Must have active client transmitting)
    ps_out = flow_collector._run_cmd(["ps", "-ef"])
    client_procs = [l for l in ps_out.splitlines() if "iperf -c" in l and "grep" not in l]
    print("\n[1] Anomaly 1: Traffic Flood (iperf h1 -> h4):")
    if client_procs:
        print("    STATUS: ACTIVE (Flood client actively transmitting)")
        for p in client_procs:
            print("    " + p)
    else:
        print("    STATUS: INACTIVE (No flood traffic being generated)")

    # 2. Check suspicious drop flow (Must have priority=50000 AND action=drop)
    flows_raw = flow_collector._run_cmd(["ovs-ofctl", "-O", "OpenFlow13", "dump-flows", "s1"])
    drop_rules = [l for l in flows_raw.splitlines() if "50000" in l and "drop" in l.lower()]
    print("\n[2] Anomaly 2: Rogue DROP Flow on s1 (h2 blackhole):")
    if drop_rules:
        print("    STATUS: ACTIVE (Rogue DROP rule is installed)")
        for m in drop_rules:
            print("    " + m.strip())
    else:
        print("    STATUS: INACTIVE (No rogue DROP rule installed)")
    print("=" * 65)

if __name__ == "__main__":
    check_status()
