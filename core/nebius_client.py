"""Minimal OpenAI-compatible client for Nebius Token Factory."""

import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI


NEBIUS_BASE_URL = "https://api.tokenfactory.nebius.com/v1/"
NEBIUS_MODEL = "nvidia/Nemotron-3_5-Lightning"


def get_nebius_client() -> OpenAI:
    """Load the project environment and create a Nebius client."""
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    api_key = os.getenv("NEBIUS_API_KEY", "").strip()
    if not api_key:
        raise ValueError("Set NEBIUS_API_KEY in .env before running the connectivity check.")
    return OpenAI(
        api_key=api_key,
        base_url=NEBIUS_BASE_URL,
        timeout=60.0,
        max_retries=0,
    )


def check_nebius_connection() -> str:
    """Send a minimal prompt and return the response text."""
    with get_nebius_client() as client:
        response = client.chat.completions.create(
            model=NEBIUS_MODEL,
            messages=[{"role": "user", "content": "Reply with exactly: OK"}],
        )
    return (response.choices[0].message.content or "").strip()
