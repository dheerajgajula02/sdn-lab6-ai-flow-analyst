#!/usr/bin/env python3
"""
CSCI 5280 - Lab 6: Objective 1, Step 4
Inject Anomaly 2: Manually install a suspicious/rogue high-priority DROP rule on switch s1.
Drops all frames originating from host h2 (MAC 00:00:00:00:00:02).
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import flow_collector

RULE = "priority=50000,dl_src=00:00:00:00:00:02,actions=drop"

def install_drop_rule():
    print("[*] Installing Anomaly 2: Rogue DROP rule on switch s1...")
    print(f"    Match Rule: {RULE}")
    
    # Install flow rule via OpenFlow 1.3
    flow_collector._run_cmd(["ovs-ofctl", "-O", "OpenFlow13", "add-flow", "s1", RULE])
    
    # Verify installation
    flows_raw = flow_collector._run_cmd(["ovs-ofctl", "-O", "OpenFlow13", "dump-flows", "s1"])
    matching = [l for l in flows_raw.splitlines() if "50000" in l or "00:00:00:00:00:02" in l]
    
    if matching:
        print("[+] SUCCESS: Rogue DROP rule is ACTIVE on s1!")
        for m in matching:
            print("    -> " + m.strip())
    else:
        print("[-] WARNING: Could not find installed rule on s1.")

if __name__ == "__main__":
    install_drop_rule()
