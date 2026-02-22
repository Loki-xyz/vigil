"""
Tests for vigil.captcha_solver — LLM-based captcha solving.

All Anthropic API calls are mocked.
"""

from __future__ import annotations

from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from vigil.captcha_solver import LLMCaptchaSolver, get_captcha_solver, reset_solver
from vigil.sc_client import SCCaptchaError


def _make_captcha_image_bytes() -> bytes:
    """Create a minimal PNG image for testing."""
    from PIL import Image

    img = Image.new("L", (150, 50), color=255)
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture(autouse=True)
def _reset_solver_cache():
    """Reset solver singleton between tests."""
    reset_solver()
    yield
    reset_solver()


def _mock_anthropic_response(text: str) -> MagicMock:
    """Build a mock Anthropic messages.create response."""
    content_block = MagicMock()
    content_block.text = text
    resp = MagicMock()
    resp.content = [content_block]
    return resp


class TestLLMCaptchaSolver:
    """Tests for LLMCaptchaSolver."""

    async def test_solve_addition(self):
        solver = LLMCaptchaSolver(api_key="test-key", model="test-model")
        solver._client = MagicMock()
        solver._client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response("8")
        )

        result = await solver.solve(_make_captcha_image_bytes())
        assert result == 8

    async def test_solve_with_extra_text(self):
        """Model returns some extra text around the number."""
        solver = LLMCaptchaSolver(api_key="test-key", model="test-model")
        solver._client = MagicMock()
        solver._client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response("The answer is 15.")
        )

        result = await solver.solve(_make_captcha_image_bytes())
        assert result == 15

    async def test_solve_negative_result(self):
        solver = LLMCaptchaSolver(api_key="test-key", model="test-model")
        solver._client = MagicMock()
        solver._client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response("-3")
        )

        result = await solver.solve(_make_captcha_image_bytes())
        assert result == -3

    async def test_solve_api_error_raises_captcha_error(self):
        import anthropic

        solver = LLMCaptchaSolver(api_key="test-key", model="test-model")
        solver._client = MagicMock()
        solver._client.messages.create = AsyncMock(
            side_effect=anthropic.APIError(
                message="rate limited",
                request=MagicMock(),
                body=None,
            )
        )

        with pytest.raises(SCCaptchaError, match="LLM API error"):
            await solver.solve(_make_captcha_image_bytes())

    async def test_solve_non_numeric_response_raises(self):
        solver = LLMCaptchaSolver(api_key="test-key", model="test-model")
        solver._client = MagicMock()
        solver._client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response("I cannot read this image")
        )

        with pytest.raises(SCCaptchaError, match="non-numeric"):
            await solver.solve(_make_captcha_image_bytes())

    def test_missing_api_key_raises(self):
        with patch("vigil.captcha_solver.settings") as mock_settings:
            mock_settings.sc_captcha_llm_api_key = ""
            mock_settings.sc_captcha_llm_model = "test-model"
            with pytest.raises(ValueError, match="VIGIL_SC_CAPTCHA_LLM_API_KEY"):
                LLMCaptchaSolver()

    async def test_sends_correct_image_payload(self):
        """Verify the image is base64-encoded and sent with correct media type."""
        import base64

        solver = LLMCaptchaSolver(api_key="test-key", model="test-model")
        solver._client = MagicMock()
        solver._client.messages.create = AsyncMock(
            return_value=_mock_anthropic_response("42")
        )

        image_bytes = _make_captcha_image_bytes()
        await solver.solve(image_bytes)

        call_kwargs = solver._client.messages.create.call_args.kwargs
        assert call_kwargs["max_tokens"] == 16
        assert call_kwargs["model"] == "test-model"

        content = call_kwargs["messages"][0]["content"]
        image_block = content[0]
        assert image_block["type"] == "image"
        assert image_block["source"]["media_type"] == "image/png"
        assert image_block["source"]["data"] == base64.b64encode(image_bytes).decode("ascii")


class TestGetCaptchaSolver:
    """Tests for the get_captcha_solver factory."""

    def test_returns_llm_solver(self):
        with patch("vigil.captcha_solver.settings") as mock_settings:
            mock_settings.sc_captcha_llm_api_key = "test-key"
            mock_settings.sc_captcha_llm_model = "test-model"
            solver = get_captcha_solver()
            assert isinstance(solver, LLMCaptchaSolver)

    def test_caches_solver_instance(self):
        with patch("vigil.captcha_solver.settings") as mock_settings:
            mock_settings.sc_captcha_llm_api_key = "test-key"
            mock_settings.sc_captcha_llm_model = "test-model"
            solver1 = get_captcha_solver()
            solver2 = get_captcha_solver()
            assert solver1 is solver2

    def test_missing_api_key_raises(self):
        with patch("vigil.captcha_solver.settings") as mock_settings:
            mock_settings.sc_captcha_llm_api_key = ""
            mock_settings.sc_captcha_llm_model = "test-model"
            with pytest.raises(ValueError, match="VIGIL_SC_CAPTCHA_LLM_API_KEY"):
                get_captcha_solver()

    def test_reset_solver_clears_cache(self):
        with patch("vigil.captcha_solver.settings") as mock_settings:
            mock_settings.sc_captcha_llm_api_key = "test-key"
            mock_settings.sc_captcha_llm_model = "test-model"
            solver1 = get_captcha_solver()
            reset_solver()
            solver2 = get_captcha_solver()
            assert solver1 is not solver2
