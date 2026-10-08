#!/usr/bin/env python3
"""
CSCI 5280 - Lab 6: Objective 1, Step 4
Stop Anomaly 1: Terminate all iperf processes.
"""

import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import flow_collector

def stop_flood():
    print("[*] Stopping Anomaly 1: Terminating iperf traffic flood...")
    flow_collector._run_cmd(["killall", "-9", "iperf"])
    flow_collector._run_cmd(["pkill", "-9", "iperf"])
    print("[+] SUCCESS: Traffic flood stopped.")

if __name__ == "__main__":
    stop_flood()
