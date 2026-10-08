You MUST respond ONLY with a valid JSON object matching the exact schema below.
Do not include any introductory remarks, preamble, explanations, or markdown fences (no ```json or ```).

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
