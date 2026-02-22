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

    # Notification preferences
    notification_email_enabled: bool = True
    notification_email_recipients: str = ""
    daily_digest_enabled: bool = True

    # Polling
    polling_enabled: bool = True
    first_poll_lookback_days: int = 4

    # SC Website Scraper
    sc_scraper_enabled: bool = False
    sc_scrape_schedule_hours: str = "8,17"
    sc_base_url: str = "https://www.sci.gov.in"
    sc_request_timeout_seconds: int = 60
    sc_max_retries: int = 3
    sc_captcha_max_attempts: int = 5
    sc_rate_limit_seconds: float = 3.0
    sc_lookback_days: int = 4
    sc_pdf_download_enabled: bool = False
    # Captcha solver
    sc_captcha_solver: str = "llm"  # "llm" | "local"
    sc_captcha_llm_api_key: str = ""
    sc_captcha_llm_model: str = "claude-haiku-4-5-20251001"

    # App
    timezone: str = "Asia/Kolkata"

    model_config = {
        "env_file": ".env",
        "env_prefix": "VIGIL_",
    }


settings = Settings()
