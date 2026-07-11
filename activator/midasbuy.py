"""
Модуль активации купонов на midasbuy.com.

Стратегия (по RESEARCH.md):
  1. Пытаемся через httpx + сессионные куки (быстро)
  2. Если HTTP не работает → fallback через Playwright (надёжно)
"""
import asyncio
from dataclasses import dataclass
from enum import Enum

import httpx
from loguru import logger

from config.settings import settings
from activator.browser import BrowserManager
from activator.exceptions import (
    ActivatorError,
    CouponAlreadyUsedError,
    CouponExpiredError,
    CouponFlaggedError,
    CouponInvalidError,
    CouponTimeoutError,
    LoginError,
    RateLimitError,
    SessionExpiredError,
)


class RedeemResult(str, Enum):
    """Результат активации купона."""
    SUCCESS = "success"
    INVALID = "invalid"
    EXPIRED = "expired"
    ALREADY_USED = "already_used"
    TIMEOUT = "timeout"
    FLAGGED = "flagged"
    ERROR = "error"
    SESSION_EXPIRED = "session_expired"
    RATE_LIMITED = "rate_limited"


@dataclass
class ActivationResult:
    """Результат попытки активации."""
    result: RedeemResult
    message: str
    raw_response: dict | None = None


# Маппинг сообщений ошибок из JS (RESEARCH.md) на наши результаты
_ERROR_MAP = {
    "expired": RedeemResult.EXPIRED,
    "invalid": RedeemResult.INVALID,
    "already been used": RedeemResult.ALREADY_USED,
    "already been redeemed": RedeemResult.ALREADY_USED,
    "timed out": RedeemResult.TIMEOUT,
    "flagged for additional review": RedeemResult.FLAGGED,
    "verification failed": RedeemResult.FLAGGED,
    "system error": RedeemResult.ERROR,
    "format error": RedeemResult.INVALID,
    "banned": RedeemResult.ERROR,
}


class MidasBuyActivator:
    """
    Активатор купонов на midasbuy.com.
    Использует httpx для прямых API-вызовов с fallback на Playwright.
    """

    def __init__(self, browser_manager: BrowserManager) -> None:
        self._browser = browser_manager
        self._http_client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        """Инициализация: запуск браузера + логин."""
        await self._browser.start()

        # Пытаемся авторизоваться
        try:
            await self._browser.login()
        except LoginError as e:
            logger.error("Не удалось авторизоваться: {}", e)
            raise

        # Создаём httpx клиент с куками из браузера
        await self._refresh_http_client()

    async def stop(self) -> None:
        """Остановка."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        await self._browser.stop()

    async def _refresh_http_client(self) -> None:
        """Обновить httpx клиент с актуальными куками."""
        if self._http_client:
            await self._http_client.aclose()

        cookies = await self._browser.get_cookies_dict()
        self._http_client = httpx.AsyncClient(
            cookies=cookies,
            headers={
                "Content-Type": "application/json",
                "User-Agent": (
                    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                    "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                    "Version/17.0 Mobile/15E148 Safari/604.1"
                ),
                "Referer": settings.midasbuy_coupon_url,
                "Origin": "https://www.midasbuy.com",
            },
            timeout=30.0,
            http2=True,
        )
        logger.debug("HTTP клиент обновлён с {} куками", len(cookies))

    # ── Main API ──────────────────────────────────────────────

    async def activate_coupon(self, coupon_code: str) -> ActivationResult:
        """
        Активировать купон. Сначала через HTTP API, потом fallback Playwright.

        Args:
            coupon_code: Код купона для активации.

        Returns:
            ActivationResult с результатом.
        """
        logger.info("Активация купона: {}", coupon_code)

        # Стратегия 1: HTTP API
        try:
            result = await self._activate_via_http(coupon_code)
            if result.result != RedeemResult.SESSION_EXPIRED:
                return result
            # Сессия истекла — перелогиниваемся
            logger.warning("Сессия истекла, перелогиниваемся...")
            await self._relogin()
            result = await self._activate_via_http(coupon_code)
            if result.result != RedeemResult.SESSION_EXPIRED:
                return result
        except Exception as e:
            logger.warning("HTTP API не удался: {}, пробуем Playwright...", e)

        # Стратегия 2: Playwright fallback
        try:
            return await self._activate_via_browser(coupon_code)
        except Exception as e:
            logger.error("Playwright fallback тоже не удался: {}", e)
            return ActivationResult(
                result=RedeemResult.ERROR,
                message=f"Все методы активации не сработали: {e}",
            )

    # ── HTTP API activation ───────────────────────────────────

    async def _activate_via_http(self, coupon_code: str) -> ActivationResult:
        """Попытка активации через прямой HTTP API."""
        if not self._http_client:
            await self._refresh_http_client()

        try:
            response = await self._http_client.post(
                settings.midasbuy_coupon_api,
                json={"couponCode": coupon_code},
            )
        except httpx.TimeoutException:
            return ActivationResult(
                result=RedeemResult.TIMEOUT,
                message="Таймаут запроса к API",
            )
        except httpx.HTTPError as e:
            return ActivationResult(
                result=RedeemResult.ERROR,
                message=f"HTTP ошибка: {e}",
            )

        # Проверяем rate limiting
        remaining = response.headers.get("x-ratelimit-remaining")
        if remaining and int(remaining) <= 1:
            logger.warning("Rate limit почти исчерпан: remaining={}", remaining)

        if response.status_code == 429:
            return ActivationResult(
                result=RedeemResult.RATE_LIMITED,
                message="Превышен лимит запросов. Попробуйте позже.",
            )

        if response.status_code == 401:
            return ActivationResult(
                result=RedeemResult.SESSION_EXPIRED,
                message="Сессия истекла (401 INVALID_AUTHORIZATION)",
            )

        try:
            data = response.json()
        except Exception:
            data = {"raw": response.text}

        logger.debug("API ответ [{}]: {}", response.status_code, data)

        if response.status_code == 200:
            return self._parse_api_response(data)

        # Пытаемся извлечь сообщение об ошибке
        error_msg = data.get("message", data.get("msg", str(data)))
        return self._classify_error(error_msg, data)

    def _parse_api_response(self, data: dict) -> ActivationResult:
        """Парсинг успешного ответа API."""
        # Проверяем наличие ошибки в ответе (может быть 200 но с ошибкой)
        ret_code = data.get("ret", data.get("code", data.get("retCode", 0)))
        message = data.get("message", data.get("msg", ""))

        if ret_code == 0 or ret_code == "0":
            return ActivationResult(
                result=RedeemResult.SUCCESS,
                message="Купон успешно активирован!",
                raw_response=data,
            )

        return self._classify_error(message, data)

    def _classify_error(self, message: str, raw: dict) -> ActivationResult:
        """Классификация ошибки по тексту сообщения."""
        msg_lower = message.lower()

        for pattern, result_type in _ERROR_MAP.items():
            if pattern in msg_lower:
                return ActivationResult(
                    result=result_type,
                    message=message,
                    raw_response=raw,
                )

        return ActivationResult(
            result=RedeemResult.ERROR,
            message=message or "Неизвестная ошибка",
            raw_response=raw,
        )

    # ── Browser fallback activation ───────────────────────────

    async def _activate_via_browser(self, coupon_code: str) -> ActivationResult:
        """
        Fallback: активация через Playwright (полная браузерная автоматизация).
        """
        logger.info("Fallback: активация через Playwright для {}", coupon_code)

        page = await self._browser.get_page()

        # Навигируемся на страницу купонов
        await page.goto(
            settings.midasbuy_coupon_url,
            wait_until="domcontentloaded",
            timeout=settings.browser_timeout,
        )
        await page.wait_for_timeout(3000)

        # Ищем поле ввода купона
        input_selectors = [
            'input[placeholder*="coupon" i]',
            'input[placeholder*="code" i]',
            'input[placeholder*="купон" i]',
            'input[placeholder*="код" i]',
            'input[placeholder*="redeem" i]',
            'input[type="text"]',
        ]

        input_filled = False
        for sel in input_selectors:
            try:
                inp = page.locator(sel).first
                if await inp.is_visible(timeout=3000):
                    await inp.fill(coupon_code)
                    input_filled = True
                    logger.info("Купон введён через: {}", sel)
                    break
            except Exception:
                continue

        if not input_filled:
            return ActivationResult(
                result=RedeemResult.ERROR,
                message="Не удалось найти поле ввода купона",
            )

        await page.wait_for_timeout(500)

        # Нажимаем кнопку активации
        submit_selectors = [
            'button:has-text("Redeem")',
            'button:has-text("Активировать")',
            'button:has-text("Применить")',
            'button:has-text("Submit")',
            'button:has-text("Use")',
        ]

        submitted = False
        for sel in submit_selectors:
            try:
                btn = page.locator(sel).first
                if await btn.is_visible(timeout=2000):
                    await btn.click()
                    submitted = True
                    logger.info("Кнопка нажата: {}", sel)
                    break
            except Exception:
                continue

        if not submitted:
            return ActivationResult(
                result=RedeemResult.ERROR,
                message="Не удалось найти кнопку активации",
            )

        # Ждём результат
        await page.wait_for_timeout(5000)

        # Пытаемся прочитать результат со страницы
        result_text = ""
        result_selectors = [
            '[class*="result"]',
            '[class*="message"]',
            '[class*="toast"]',
            '[class*="alert"]',
            '[class*="tip"]',
            '[class*="notice"]',
        ]

        for sel in result_selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible(timeout=2000):
                    result_text = await el.text_content()
                    if result_text:
                        break
            except Exception:
                continue

        if not result_text:
            # Делаем скриншот
            try:
                from pathlib import Path
                screenshot_path = Path("data") / f"coupon_{coupon_code}.png"
                await page.screenshot(path=str(screenshot_path))
                logger.info("Скриншот результата: {}", screenshot_path)
            except Exception:
                pass

            return ActivationResult(
                result=RedeemResult.ERROR,
                message="Не удалось определить результат активации (см. скриншот)",
            )

        return self._classify_error(result_text, {"browser_result": result_text})

    # ── Helpers ───────────────────────────────────────────────

    async def _relogin(self) -> None:
        """Переавторизоваться."""
        logger.info("Переавторизация...")
        await self._browser.stop()
        await self._browser.start()
        await self._browser.login()
        await self._refresh_http_client()
        logger.info("Переавторизация завершена")
