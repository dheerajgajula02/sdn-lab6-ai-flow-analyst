IMPORTANT: Your previous output failed JSON validation:
{error}

Ensure you return ONLY the JSON object, strictly valid RFC 8259 JSON, starting with '{' and ending with '}'.
Match this schema:
{
  "network_health": "normal" | "warning" | "critical",
  "anomalies_detected": [
    {
      "type": "<string>",
      "affected_device": "<string>",
      "description": "<string>",
      "severity": "low" | "medium" | "high"
    }
  ],
  "summary": "<string>"
}
No markdown codeblocks, no explanations outside the JSON object.
