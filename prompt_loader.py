#!/usr/bin/env python3
"""
Prompt Loader Module for SDN AI Flow Analyst
============================================
Decouples natural language prompt engineering from Python execution logic.
Loads prompt templates from the 'prompts/' directory with optional dynamic formatting
and topology context injection (e.g. architecture.md).
"""

import os
from pathlib import Path

# Directory holding prompt templates
PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"
ARCHITECTURE_FILE = Path(__file__).resolve().parent / "skills" / "sdn-flow-analyst" / "references" / "architecture.md"


def load_prompt(filename: str, fallback: str = "", **kwargs) -> str:
    """
    Reads a prompt file from the prompts directory and applies variable formatting.
    If the file does not exist, returns the provided fallback string.
    """
    filepath = PROMPTS_DIR / filename
    if filepath.is_file():
        try:
            content = filepath.read_text(encoding="utf-8").strip()
            if kwargs:
                content = content.format(**kwargs)
            return content
        except Exception as e:
            print(f"[!] Warning: Error reading prompt file '{filename}': {e}")
    return fallback.format(**kwargs) if kwargs else fallback


def get_terminal_agent_system_prompt(include_architecture: bool = False) -> str:
    """
    Loads the system prompt for the terminal agent.
    Optionally appends the network architecture specification from architecture.md.
    """
    base_prompt = load_prompt("terminal_agent_system.md")
    if include_architecture and ARCHITECTURE_FILE.is_file():
        arch_content = ARCHITECTURE_FILE.read_text(encoding="utf-8").strip()
        return f"{base_prompt}\n\n## Topology & Architecture Context:\n{arch_content}"
    return base_prompt
