# OpenFlow 1.3 & Ryu REST API Reference

## Useful Ryu REST Endpoints

Controller base URL: `http://100.110.3.67:8080` (or `http://10.224.78.132:8080`)

### 1. Get Connected Switches (DPIDs)
```bash
curl -s http://100.110.3.67:8080/stats/switches
# Response: [1, 2]
```

### 2. Dump Flow Entries for a Switch
```bash
# Switch 1 (s1)
curl -s http://100.110.3.67:8080/stats/flow/1
# Switch 2 (s2)
curl -s http://100.110.3.67:8080/stats/flow/2
```

### 3. Dump Port Statistics
```bash
curl -s http://100.110.3.67:8080/stats/port/1
curl -s http://100.110.3.67:8080/stats/port/2
```

### 4. Delete Flow Entry (Strict)
```bash
curl -X POST -d '{
    "dpid": 1,
    "priority": 10000,
    "match": {"dl_src": "00:00:00:00:00:02"}
}' http://100.110.3.67:8080/stats/flowentry/delete_strict
```

### 5. Clear All Flows for a Switch
```bash
curl -X DELETE http://100.110.3.67:8080/stats/flowentry/clear/1
curl -X DELETE http://100.110.3.67:8080/stats/flowentry/clear/2
```

## OVS CLI Commands (on Mininet VM)

```bash
# Show OVS bridges and ports
sudo ovs-vsctl show

# Dump flow table
sudo ovs-ofctl -O OpenFlow13 dump-flows s1
sudo ovs-ofctl -O OpenFlow13 dump-flows s2

# Dump port stats
sudo ovs-ofctl -O OpenFlow13 dump-ports s1
sudo ovs-ofctl -O OpenFlow13 dump-ports s2
```
