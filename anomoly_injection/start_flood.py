#!/usr/bin/env python3
"""
CSCI 5280 - Lab 6: Objective 1, Step 4
Inject Anomaly 1: High-volume UDP traffic flood from h1 to h4 using iperf (50 Mbps).
"""

import sys
import os
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
import flow_collector

def start_flood():
    print("[*] Starting Anomaly 1: High-Volume Traffic Flood (h1 -> h4)...")
    
    # 1. Terminate any previous iperf instances
    flow_collector._run_cmd(["killall", "-9", "iperf"])
    
    # 2. Launch background server on h4 (PID 27570) and background client on h1 (PID 27563)
    cmd = (
        "nohup mnexec -a 27570 iperf -s -u -p 5001 </dev/null >/dev/null 2>&1 & "
        "sleep 0.2; "
        "nohup mnexec -a 27563 iperf -c 10.0.0.4 -u -b 50M -t 3600 </dev/null >/dev/null 2>&1 &"
    )
    flow_collector._run_cmd(["bash", "-c", f"\"{cmd}\""])
    time.sleep(1)
    
    # 3. Verify running client process
    ps_out = flow_collector._run_cmd(["ps", "-ef"])
    client_procs = [l for l in ps_out.splitlines() if "iperf -c" in l and "grep" not in l]
    
    if client_procs:
        print("[+] SUCCESS: Traffic flood is ACTIVE!")
        for p in client_procs:
            print("    -> " + p)
    else:
        print("[-] WARNING: Could not detect running iperf client.")

if __name__ == "__main__":
    start_flood()
