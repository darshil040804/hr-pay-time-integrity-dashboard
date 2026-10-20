"""OpenAI-compatible chat client for the development-time AI scripts.

Used only by scripts in ai/. The Streamlit app and pytest never call it.

Configuration comes from environment variables (normally set in .env, which
is gitignored; see .env.example):
    AI_BASE_URL               OpenAI-compatible endpoint (e.g. Groq)
    AI_API_KEY                API key. Never printed or logged.
    AI_MODEL                  Model name
    AI_REQUEST_DELAY_SECONDS  Minimum seconds between requests (default 3)

Free tiers are rate limited, so the client waits between requests and
retries HTTP 429 responses with exponential backoff.

Smoke test (makes one small request):
    python -m ai.client
"""

import json
import os
import re
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI, RateLimitError

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

DEFAULT_REQUEST_DELAY_SECONDS = 3.0
MAX_RETRIES = 5
BACKOFF_BASE_SECONDS = 5.0
MAX_BACKOFF_SECONDS = 60.0
PLACEHOLDER_KEYS = {"", "your-key-here"}

_CODE_FENCE = re.compile(r"```[a-zA-Z]*\s*\n?(.*?)\n?\s*```", re.DOTALL)


class AIConfigError(RuntimeError):
    """Raised when the AI environment variables are missing or invalid."""


def load_config() -> dict:
    """Read and check the AI settings. Error messages never include the key."""
    config = {
        "base_url": os.getenv("AI_BASE_URL", "").strip(),
        "api_key": os.getenv("AI_API_KEY", "").strip(),
        "model": os.getenv("AI_MODEL", "").strip(),
    }
    missing = [name for name, key in [("AI_BASE_URL", "base_url"), ("AI_MODEL", "model")] if not config[key]]
    if config["api_key"] in PLACEHOLDER_KEYS:
        missing.append("AI_API_KEY")
    if missing:
        raise AIConfigError(
            f"Missing AI setting(s): {', '.join(missing)}. Copy .env.example to .env and fill them in."
        )

    delay = os.getenv("AI_REQUEST_DELAY_SECONDS", "").strip()
    try:
        config["request_delay"] = float(delay) if delay else DEFAULT_REQUEST_DELAY_SECONDS
    except ValueError:
        raise AIConfigError(f"AI_REQUEST_DELAY_SECONDS must be a number, got {delay!r}.") from None
    if config["request_delay"] < 0:
        raise AIConfigError("AI_REQUEST_DELAY_SECONDS cannot be negative.")
    return config


def strip_code_fences(text: str) -> str:
    """Return the content of the first markdown code fence, or the text itself.

    Some providers (e.g. Groq) wrap JSON in ```json ... ``` even when asked not to.
    """
    match = _CODE_FENCE.search(text)
    return (match.group(1) if match else text).strip()


def parse_json(text: str):
    """Parse a model reply as JSON, tolerating markdown code fences."""
    return json.loads(strip_code_fences(text))


class AIClient:
    def __init__(self):
        config = load_config()
        self.model = config["model"]
        self.request_delay = config["request_delay"]
        # Retries are handled here so the backoff is visible and predictable.
        self._client = OpenAI(base_url=config["base_url"], api_key=config["api_key"], max_retries=0)
        self._last_request_at = None

    def chat(self, messages: list[dict], temperature: float = 0.2) -> str:
        """Send a chat request and return the reply text."""
        for attempt in range(MAX_RETRIES + 1):
            self._wait_between_requests()
            try:
                response = self._client.chat.completions.create(
                    model=self.model, messages=messages, temperature=temperature,
                )
                return response.choices[0].message.content or ""
            except RateLimitError as error:
                if attempt == MAX_RETRIES:
                    raise
                wait = _retry_after_seconds(error) or BACKOFF_BASE_SECONDS * 2 ** attempt
                wait = min(wait, MAX_BACKOFF_SECONDS)
                print(f"  Rate limited (HTTP 429). Retry {attempt + 1}/{MAX_RETRIES} in {wait:.0f}s...")
                time.sleep(wait)

    def chat_json(self, messages: list[dict], temperature: float = 0.2):
        """Send a chat request and parse the reply as JSON (code fences stripped)."""
        return parse_json(self.chat(messages, temperature))

    def _wait_between_requests(self):
        if self._last_request_at is not None:
            remaining = self.request_delay - (time.monotonic() - self._last_request_at)
            if remaining > 0:
                time.sleep(remaining)
        self._last_request_at = time.monotonic()


def _retry_after_seconds(error: RateLimitError) -> float | None:
    """Seconds the server asked us to wait (Retry-After header), if it said."""
    try:
        return float(error.response.headers.get("retry-after"))
    except (AttributeError, TypeError, ValueError):
        return None


if __name__ == "__main__":
    client = AIClient()
    print(f"Model: {client.model}  |  delay between requests: {client.request_delay}s")
    reply = client.chat_json([{"role": "user", "content": 'Reply with only this JSON: {"ok": true}'}])
    print("Parsed reply:", reply)
