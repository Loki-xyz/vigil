"""
Settings from environment variables.

All config is loaded via Pydantic Settings with the VIGIL_ prefix.
"""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Supabase
    supabase_url: str = ""
    supabase_service_role_key: str = ""

    # Indian Kanoon API
    ik_api_token: str = ""
    ik_api_base_url: str = "https://api.indiankanoon.org"
    ik_api_timeout_seconds: int = 30
    ik_api_max_retries: int = 3

    # Email notifications
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_username: str = ""
    smtp_password: str = ""
    smtp_from_email: str = ""
    smtp_use_tls: bool = True

    # Slack notifications
    slack_webhook_url: str = ""

    # Notification preferences
    notification_email_enabled: bool = True
    notification_slack_enabled: bool = False
    notification_email_recipients: str = ""
    daily_digest_enabled: bool = True

    # Polling
    polling_enabled: bool = True
    first_poll_lookback_days: int = 4

    # App
    timezone: str = "Asia/Kolkata"

    model_config = {
        "env_file": ".env",
        "env_prefix": "VIGIL_",
    }


settings = Settings()
