You MUST respond ONLY with a valid JSON object matching the exact schema below.
Do not include any introductory remarks, preamble, explanations, or markdown fences (no ```json or ```).

Evaluation Guidelines:
- "normal": Nominal baseline operation. Low traffic volume (ping/ARP), standard L2 learning rules, zero packet drops, and no rogue or high-priority DROP rules.
- "warning": Moderate anomalies, such as suspicious high-priority rules (priority >= 1000) or isolated host blackholes that have not yet caused broad network congestion.
- "critical": Active high-volume traffic floods (e.g., hundreds of thousands of packets or megabytes/gigabytes of unthrottled traffic) or severe packet loss impacting multiple devices.

Schema:
{
  "network_health": "normal" | "warning" | "critical",
  "anomalies_detected": [
    {
      "type": "<string: e.g. Traffic Flood, Rogue Flow Rule, Host Blackhole>",
      "affected_device": "<string: e.g. s1-eth1, s1, h2>",
      "description": "<string: explanation of what was found>",
      "severity": "low" | "medium" | "high"
    }
  ],
  "summary": "<string: concise executive summary of network state>"
}
