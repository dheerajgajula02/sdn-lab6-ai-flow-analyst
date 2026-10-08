#!/usr/bin/env python3
"""
CSCI 5280 - Lab 6: Objective 1, Step 4
Remove Anomaly 2: Delete suspicious DROP rule from switch s1.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import flow_collector

def remove_drop_rule():
    print("[*] Removing Anomaly 2: Deleting rogue DROP rule from switch s1...")
    flow_collector._run_cmd(["ovs-ofctl", "-O", "OpenFlow13", "del-flows", "s1", "dl_src=00:00:00:00:00:02"])
    print("[+] SUCCESS: Rogue DROP rule removed from s1.")

if __name__ == "__main__":
    remove_drop_rule()
