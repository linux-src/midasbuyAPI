"""
Конфигурация проекта через pydantic-settings.
Загружает переменные из .env файла.
"""
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


# Корень проекта
BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Основные настройки приложения."""

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Telegram ──────────────────────────────────────────────
    telegram_bot_token: str = "your_bot_token_here"
    admin_chat_id: str = "your_admin_telegram_id"

    # ── MidasBuy Account ──────────────────────────────────────
    midasbuy_email: str = ""
    midasbuy_password: str = ""

    # ── MidasBuy URLs ─────────────────────────────────────────
    midasbuy_coupon_url: str = (
        "https://www.midasbuy.com/shop/pagedoo/ct1744785094_QMGQJMGD"
        "/mobile/index.html?from=self.midasbuy_saas"
        "&adtag=couponManage#/pages/p-wgbu/"
    )
    midasbuy_login_url: str = (
        "https://www.midasbuy.com/apps/login/home/ru"
        "?appid=1450027575&lang=ru#login"
    )
    midasbuy_coupon_api: str = (
        "https://www.midasbuy.com/frontend/api/midasbuy/v1/coupon/redeem"
    )

    # ── Database ──────────────────────────────────────────────
    database_url: str = f"sqlite+aiosqlite:///{BASE_DIR / 'data' / 'coupons.db'}"

    # ── Playwright / Browser ──────────────────────────────────
    session_file: str = str(BASE_DIR / "data" / "session.json")
    headless: bool = True
    browser_timeout: int = 60000  # ms

    # ── Activator ─────────────────────────────────────────────
    max_retries: int = 3
    retry_delay_seconds: int = 10
    request_delay_seconds: int = 2

    # ── Logging ───────────────────────────────────────────────
    log_level: str = "INFO"
    log_file: str = str(BASE_DIR / "logs" / "bot.log")

    # ── Rate Limiting ─────────────────────────────────────────
    rate_limit_max_coupons: int = 5       # макс купонов за период
    rate_limit_period_seconds: int = 3600  # период (1 час)


# Глобальный синглтон
settings = Settings()
