"""Tests for vigil.config — Settings class (pydantic_settings.BaseSettings)."""

from __future__ import annotations

import os

import pytest

from vigil.config import Settings


@pytest.mark.unit
def test_default_values(monkeypatch):
    """Instantiate Settings() with no env vars — all defaults should apply."""
    # Clear any VIGIL_ env vars set by conftest
    for key in list(os.environ):
        if key.startswith("VIGIL_"):
            monkeypatch.delenv(key)

    s = Settings(_env_file=None)

    assert s.supabase_url == ""
    assert s.supabase_service_role_key == ""
    assert s.ik_api_token == ""
    assert s.ik_api_base_url == "https://api.indiankanoon.org"
    assert s.ik_api_timeout_seconds == 30
    assert s.ik_api_max_retries == 3
    assert s.smtp_host == ""
    assert s.smtp_port == 587
    assert s.smtp_username == ""
    assert s.smtp_password == ""
    assert s.smtp_from_email == ""
    assert s.smtp_use_tls is True
    assert s.slack_webhook_url == ""
    assert s.polling_enabled is True
    assert s.timezone == "Asia/Kolkata"


@pytest.mark.unit
def test_env_prefix_loading(monkeypatch):
    """VIGIL_ prefix: VIGIL_IK_API_TOKEN should populate ik_api_token."""
    monkeypatch.setenv("VIGIL_IK_API_TOKEN", "tok_abc123")
    s = Settings(_env_file=None)
    assert s.ik_api_token == "tok_abc123"


@pytest.mark.unit
def test_all_env_vars_loaded(monkeypatch):
    """Set every VIGIL_* env var and verify all fields load correctly."""
    env_map = {
        "VIGIL_SUPABASE_URL": "https://abc.supabase.co",
        "VIGIL_SUPABASE_SERVICE_ROLE_KEY": "svc_key_123",
        "VIGIL_IK_API_TOKEN": "ik_tok_456",
        "VIGIL_IK_API_BASE_URL": "https://custom.ik.api",
        "VIGIL_IK_API_TIMEOUT_SECONDS": "60",
        "VIGIL_IK_API_MAX_RETRIES": "5",
        "VIGIL_SMTP_HOST": "smtp.example.com",
        "VIGIL_SMTP_PORT": "465",
        "VIGIL_SMTP_USERNAME": "user@example.com",
        "VIGIL_SMTP_PASSWORD": "s3cret",
        "VIGIL_SMTP_FROM_EMAIL": "noreply@example.com",
        "VIGIL_SMTP_USE_TLS": "false",
        "VIGIL_SLACK_WEBHOOK_URL": "https://hooks.slack.com/xxx",
        "VIGIL_POLLING_ENABLED": "true",
        "VIGIL_TIMEZONE": "UTC",
    }
    for k, v in env_map.items():
        monkeypatch.setenv(k, v)

    s = Settings(_env_file=None)

    assert s.supabase_url == "https://abc.supabase.co"
    assert s.supabase_service_role_key == "svc_key_123"
    assert s.ik_api_token == "ik_tok_456"
    assert s.ik_api_base_url == "https://custom.ik.api"
    assert s.ik_api_timeout_seconds == 60
    assert s.ik_api_max_retries == 5
    assert s.smtp_host == "smtp.example.com"
    assert s.smtp_port == 465
    assert s.smtp_username == "user@example.com"
    assert s.smtp_password == "s3cret"
    assert s.smtp_from_email == "noreply@example.com"
    assert s.smtp_use_tls is False
    assert s.slack_webhook_url == "https://hooks.slack.com/xxx"
    assert s.polling_enabled is True
    assert s.timezone == "UTC"


@pytest.mark.unit
def test_type_coercion_int(monkeypatch):
    """String env var should be coerced to int for SMTP_PORT."""
    monkeypatch.setenv("VIGIL_SMTP_PORT", "2525")
    s = Settings(_env_file=None)
    assert s.smtp_port == 2525
    assert isinstance(s.smtp_port, int)


@pytest.mark.unit
def test_type_coercion_bool(monkeypatch):
    """Bool coercion: 'false' -> False, '0' -> False."""
    monkeypatch.setenv("VIGIL_SMTP_USE_TLS", "false")
    monkeypatch.setenv("VIGIL_POLLING_ENABLED", "0")
    s = Settings(_env_file=None)
    assert s.smtp_use_tls is False
    assert s.polling_enabled is False


@pytest.mark.unit
def test_env_file_loading(monkeypatch, tmp_path):
    """Settings can load values from a .env file via _env_file."""
    # Clear VIGIL_ env vars so file values take precedence
    for key in list(os.environ):
        if key.startswith("VIGIL_"):
            monkeypatch.delenv(key)

    env_file = tmp_path / ".env"
    env_file.write_text(
        "VIGIL_SUPABASE_URL=https://from-file.supabase.co\n"
        "VIGIL_IK_API_TOKEN=file_token_789\n"
        "VIGIL_SMTP_PORT=2525\n"
    )
    s = Settings(_env_file=str(env_file))
    assert s.supabase_url == "https://from-file.supabase.co"
    assert s.ik_api_token == "file_token_789"
    assert s.smtp_port == 2525


@pytest.mark.unit
def test_empty_string_defaults(monkeypatch):
    """Fields with '' default should actually be empty strings, not None."""
    for key in list(os.environ):
        if key.startswith("VIGIL_"):
            monkeypatch.delenv(key)

    s = Settings(_env_file=None)
    assert s.supabase_url == ""
    assert s.slack_webhook_url == ""
    assert isinstance(s.supabase_url, str)
    assert isinstance(s.slack_webhook_url, str)


@pytest.mark.unit
def test_module_level_instance():
    """vigil.config exposes a module-level `settings` instance of Settings."""
    from vigil.config import settings

    assert isinstance(settings, Settings)
