"""
Captcha solver for SC website math captchas.

Uses Claude Haiku vision API to read simple math expressions
(e.g. '3 + 5', '7 x 2') and return the computed integer answer.
"""

from __future__ import annotations

import base64
import logging
import re

import anthropic

from vigil.config import settings

logger = logging.getLogger(__name__)

_CAPTCHA_PROMPT = (
    "This image shows a simple math captcha with an expression like "
    "'3 + 5' or '7 x 2' or '10 - 4'. "
    "Compute the result and return ONLY the integer answer, nothing else."
)


class LLMCaptchaSolver:
    """Solve math captchas using Claude Haiku vision API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ):
        self._api_key = api_key or settings.sc_captcha_llm_api_key
        self._model = model or settings.sc_captcha_llm_model
        if not self._api_key:
            raise ValueError(
                "VIGIL_SC_CAPTCHA_LLM_API_KEY must be set for captcha solving"
            )
        self._client = anthropic.AsyncAnthropic(api_key=self._api_key)

    async def solve(self, image_bytes: bytes) -> int:
        """Send captcha image to Claude and parse the integer answer."""
        from vigil.sc_client import SCCaptchaError

        b64 = base64.b64encode(image_bytes).decode("ascii")

        try:
            resp = await self._client.messages.create(
                model=self._model,
                max_tokens=16,
                messages=[
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image",
                                "source": {
                                    "type": "base64",
                                    "media_type": "image/png",
                                    "data": b64,
                                },
                            },
                            {"type": "text", "text": _CAPTCHA_PROMPT},
                        ],
                    }
                ],
            )
        except anthropic.APIError as e:
            raise SCCaptchaError(f"LLM API error: {e}") from e

        text = resp.content[0].text.strip()
        logger.debug("LLM captcha response: %r", text)

        match = re.search(r"-?\d+", text)
        if not match:
            raise SCCaptchaError(f"LLM returned non-numeric response: {text!r}")

        answer = int(match.group())
        logger.info("LLM captcha solver: answer=%d (raw=%r)", answer, text)
        return answer


_solver_instance: LLMCaptchaSolver | None = None


def get_captcha_solver() -> LLMCaptchaSolver:
    """Return the cached LLM captcha solver instance."""
    global _solver_instance

    if _solver_instance is not None:
        return _solver_instance

    logger.info("Initializing LLM captcha solver (model=%s)", settings.sc_captcha_llm_model)
    _solver_instance = LLMCaptchaSolver()
    return _solver_instance


def reset_solver() -> None:
    """Reset the cached solver instance (for testing)."""
    global _solver_instance
    _solver_instance = None
