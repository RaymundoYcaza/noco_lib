"""AIClient — low-level HTTP client for Ollama (and future AI providers).

Every public method returns ``AIResult`` and never raises to the caller.
"""

from __future__ import annotations

import json
import logging
import time
from typing import TYPE_CHECKING

import requests

from ai_lib.ai_result import AIResult

if TYPE_CHECKING:
    from app_core.config import TardisConfig

logger = logging.getLogger("tardis")


class AIClient:
    """HTTP client for the Ollama chat API.

    Wraps the ``/api/chat`` endpoint with JSON-mode parsing, retry
    logic, and uniform ``AIResult`` return values.

    Parameters
    ----------
    provider : str
        Provider name (e.g. ``"ollama"``).  Used for metadata only.
    model : str
        Model name (e.g. ``"gemma3:27b"``, ``"llama3"``).
    base_url : str
        Base URL of the AI provider (e.g. ``"http://localhost:11434"``).
    """

    def __init__(
        self,
        provider: str,
        model: str,
        base_url: str,
    ) -> None:
        self.provider = provider
        self.model = model
        self.base_url = base_url.rstrip("/")

        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    # ── Public API ────────────────────────────────────────────────────

    def complete(self, prompt: str, operation: str) -> AIResult:
        """Send a prompt to the AI chat endpoint and return a structured result.

        Parameters
        ----------
        prompt : str
            The fully-formatted prompt string (placeholders already
            substituted by the caller).
        operation : str
            Operation label for the result (``"correct"``, ``"classify"``,
            ``"extract"``, ``"summarize"``).

        Returns
        -------
        AIResult
            ``ok`` with the AI's answer in ``data``, or ``fail`` on any
            error (network, JSON parse, missing key).
        """
        url = f"{self.base_url}/api/chat"
        body = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "format": "json",  # Ollama JSON mode
        }

        # Attempt the request (with one retry on connection/timeout errors)
        last_exception: Exception | None = None
        for attempt in range(2):
            try:
                resp = self._session.post(url, json=body, timeout=60)
                resp.raise_for_status()
                return self._parse_response(resp, operation)
            except requests.ConnectionError as exc:
                last_exception = exc
                logger.warning(
                    "AIClient: ConnectionError on attempt %d/2: %s",
                    attempt + 1,
                    exc,
                )
                time.sleep(0.5 * (attempt + 1))
            except requests.Timeout as exc:
                last_exception = exc
                logger.warning(
                    "AIClient: Timeout on attempt %d/2: %s",
                    attempt + 1,
                    exc,
                )
                time.sleep(0.5 * (attempt + 1))
            except requests.RequestException as exc:
                # Non-retryable HTTP error (4xx, 5xx) — fail immediately
                last_exception = exc
                logger.error(
                    "AIClient: HTTP error on attempt %d/2: %s",
                    attempt + 1,
                    exc,
                )
                return AIResult.fail(
                    operation,
                    str(exc),
                    meta={"provider": self.provider, "model": self.model},
                )

        # Both attempts failed
        return AIResult.fail(
            operation,
            f"AI request failed after retries: {last_exception}",
            meta={"provider": self.provider, "model": self.model},
        )

    @classmethod
    def from_config(cls, config: "TardisConfig") -> "AIClient":
        """Create an ``AIClient`` from a ``TardisConfig`` instance.

        Parameters
        ----------
        config : TardisConfig
            Application configuration with ``ai_provider``, ``ai_model``,
            and ``ai_base_url`` fields.

        Returns
        -------
        AIClient
        """
        return cls(
            provider=config.ai_provider,
            model=config.ai_model,
            base_url=config.ai_base_url,
        )

    # ── Internal helpers ─────────────────────────────────────────────

    def _parse_response(self, resp: requests.Response, operation: str) -> AIResult:
        """Parse the Ollama chat API response into an ``AIResult``."""
        try:
            data = resp.json()
        except (json.JSONDecodeError, requests.RequestException) as exc:
            return AIResult.fail(
                operation,
                f"Failed to decode response JSON: {exc}",
                meta={"provider": self.provider, "model": self.model},
            )

        # Extract message content
        try:
            message = data.get("message", {})
            content: str = message.get("content", "")
        except (AttributeError, KeyError) as exc:
            return AIResult.fail(
                operation,
                f"Missing 'message.content' in AI response: {exc}",
                meta={"provider": self.provider, "model": self.model},
            )

        # Parse the content as JSON (Ollama JSON mode returns a JSON string)
        try:
            result_obj = json.loads(content)
        except (json.JSONDecodeError, TypeError) as exc:
            return AIResult.fail(
                operation,
                f"AI response content is not valid JSON: {exc}",
                meta={"provider": self.provider, "model": self.model},
            )

        # Extract the expected "result" key
        result_value = result_obj.get("result")
        if result_value is None:
            return AIResult.fail(
                operation,
                f"AI response JSON missing 'result' key: {result_obj}",
                meta={"provider": self.provider, "model": self.model},
            )

        # Build meta from Ollama response fields
        meta = {
            "model": data.get("model", self.model),
            "provider": self.provider,
            "prompt_tokens": data.get("prompt_eval_count", 0),
            "completion_tokens": data.get("eval_count", 0),
            "latency_ms": data.get("total_duration", 0) // 1_000_000,
        }

        return AIResult.ok(operation, data=result_value, meta=meta)
