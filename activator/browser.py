"""
Управление браузером Playwright.
Логин на midasbuy.com, сохранение и загрузка сессии.
"""
import asyncio
import json
from pathlib import Path

from loguru import logger
from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from config.settings import settings
from activator.exceptions import BrowserError, LoginError, SessionExpiredError


class BrowserManager:
    """
    Управляет жизненным циклом браузера Playwright.
    Один экземпляр на всё приложение.
    """

    def __init__(self) -> None:
        self._playwright = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None
        self._is_logged_in: bool = False

    # ── Lifecycle ─────────────────────────────────────────────

    async def start(self) -> None:
        """Запустить браузер."""
        if self._browser is not None:
            return

        logger.info("Запуск Playwright браузера (headless={})...", settings.headless)
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=settings.headless,
        )
        logger.info("Браузер запущен")

    async def stop(self) -> None:
        """Остановить браузер и освободить ресурсы."""
        if self._context:
            await self._context.close()
            self._context = None
            self._page = None
        if self._browser:
            await self._browser.close()
            self._browser = None
        if self._playwright:
            await self._playwright.stop()
            self._playwright = None
        self._is_logged_in = False
        logger.info("Браузер остановлен")

    # ── Context / Session ─────────────────────────────────────

    async def _create_context(self, storage_state: str | None = None) -> BrowserContext:
        """Создать новый контекст с мобильным viewport."""
        if self._browser is None:
            raise BrowserError("Браузер не запущен. Вызовите start() сначала.")

        kwargs = {
            "viewport": {"width": 390, "height": 844},
            "user_agent": (
                "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) "
                "AppleWebKit/605.1.15 (KHTML, like Gecko) "
                "Version/17.0 Mobile/15E148 Safari/604.1"
            ),
        }

        if storage_state and Path(storage_state).exists():
            kwargs["storage_state"] = storage_state
            logger.info("Загружена сохранённая сессия из {}", storage_state)

        return await self._browser.new_context(**kwargs)

    async def _ensure_context(self) -> None:
        """Убедиться, что контекст и страница существуют."""
        if self._context is None:
            self._context = await self._create_context(settings.session_file)
            self._page = await self._context.new_page()

    async def save_session(self) -> None:
        """Сохранить состояние сессии (куки + localStorage)."""
        if self._context is None:
            return

        session_path = Path(settings.session_file)
        session_path.parent.mkdir(parents=True, exist_ok=True)

        state = await self._context.storage_state()
        with open(session_path, "w") as f:
            json.dump(state, f, indent=2)

        logger.info("Сессия сохранена в {}", session_path)

    async def check_logged_in(self) -> bool:
        """
        Проверить, авторизован ли пользователь.
        Ориентир: cookie select_cookie=1
        """
        if self._context is None:
            return False

        cookies = await self._context.cookies("https://www.midasbuy.com")
        for cookie in cookies:
            if cookie["name"] == "select_cookie" and cookie["value"] == "1":
                self._is_logged_in = True
                return True

        self._is_logged_in = False
        return False

    # ── Login ─────────────────────────────────────────────────

    async def login(self) -> bool:
        """
        Выполнить логин на midasbuy.com через Playwright.
        Двухшаговая форма: email → Next → password → Submit.
        """
        await self._ensure_context()

        # Проверяем, может уже залогинены (из сохранённой сессии)
        if await self.check_logged_in():
            logger.info("Уже авторизованы (из сохранённой сессии)")
            return True

        logger.info("Начинаем процесс авторизации...")

        try:
            # Открываем страницу купонов
            await self._page.goto(
                settings.midasbuy_coupon_url,
                wait_until="domcontentloaded",
                timeout=settings.browser_timeout,
            )
            await self._page.wait_for_timeout(3000)

            # Ищем кнопку Sign In
            sign_in_selectors = [
                'text="Sign In"',
                'text="Sign In Midasbuy"',
                'text="Войти"',
                '[class*="sign-in"]',
                '[class*="login"]',
                'button:has-text("Sign")',
                'button:has-text("Войти")',
            ]

            clicked = False
            for sel in sign_in_selectors:
                try:
                    btn = self._page.locator(sel).first
                    if await btn.is_visible(timeout=2000):
                        await btn.click()
                        clicked = True
                        logger.info("Нажата кнопка: {}", sel)
                        break
                except Exception:
                    continue

            if not clicked:
                logger.warning("Кнопка Sign In не найдена, пробуем продолжить...")

            await self._page.wait_for_timeout(3000)

            # Собираем все фреймы для поиска элементов
            all_targets = [self._page] + list(self._page.frames)

            # ── ШАГ 1: Заполняем email ──
            email_filled = False
            email_selectors = [
                'input[type="email"]',
                'input[placeholder*="email" i]',
                'input[placeholder*="Email" i]',
                'input[name="email"]',
                'input[placeholder*="почт" i]',
                'input[name="account"]',
                'input[placeholder*="account" i]',
            ]

            for target in all_targets:
                for sel in email_selectors:
                    try:
                        inp = target.locator(sel).first
                        if await inp.is_visible(timeout=1500):
                            await inp.fill(settings.midasbuy_email)
                            email_filled = True
                            frame_name = getattr(target, 'name', 'main') or 'main'
                            logger.info("Email заполнен через: {} (frame: {})", sel, frame_name)
                            break
                    except Exception:
                        continue
                if email_filled:
                    break

            if not email_filled:
                await self._save_debug_screenshot("login_no_email")
                raise LoginError("Не удалось найти поле email")

            await self._page.wait_for_timeout(1000)

            # Обновляем список фреймов (iframe мог появиться после email)
            all_targets = [self._page] + list(self._page.frames)

            # ── ШАГ 2: Нажимаем Next / Continue (если двухшаговая форма) ──
            next_selectors = [
                'text="Продолжить"',
                'text="Continue"',
                'text="Next"',
                'text="Далее"',
                ':has-text("Продолжить")',
                ':has-text("Continue")',
                ':has-text("Next")',
                ':has-text("Далее")',
                'button:has-text("Продолжить")',
                'button:has-text("Continue")',
                'button:has-text("Next")',
                'button:has-text("Далее")',
                'div:has-text("Продолжить")',
                'button[type="submit"]',
                'button:has-text("Log In")',
                'button:has-text("Sign In")',
                'button:has-text("Войти")',
            ]

            next_clicked = False
            for target in all_targets:
                for sel in next_selectors:
                    try:
                        btn = target.locator(sel).first
                        if await btn.is_visible(timeout=1500):
                            await btn.click()
                            next_clicked = True
                            frame_name = getattr(target, 'name', 'main') or 'main'
                            logger.info("Next/Submit нажат: {} (frame: {})", sel, frame_name)
                            break
                    except Exception:
                        continue
                if next_clicked:
                    break

            # Ждём появления поля пароля (может быть двухшаговая форма)
            await self._page.wait_for_timeout(3000)

            # Обновляем список фреймов (могли появиться новые)
            all_targets = [self._page] + list(self._page.frames)

            # ── ШАГ 3: Заполняем пароль ──
            password_filled = False
            password_selectors = [
                'input[type="password"]',
                'input[placeholder*="password" i]',
                'input[name="password"]',
                'input[placeholder*="парол" i]',
                'input[placeholder*="пароль" i]',
            ]

            for target in all_targets:
                for sel in password_selectors:
                    try:
                        inp = target.locator(sel).first
                        if await inp.is_visible(timeout=2000):
                            await inp.fill(settings.midasbuy_password)
                            password_filled = True
                            frame_name = getattr(target, 'name', 'main') or 'main'
                            logger.info("Пароль заполнен через: {} (frame: {})", sel, frame_name)
                            break
                    except Exception:
                        continue
                if password_filled:
                    break

            if not password_filled:
                # Возможно, email+пароль были на одной странице и форма уже отправлена
                # Проверяем, не залогинились ли мы уже
                await self._page.wait_for_timeout(3000)
                if await self.check_logged_in():
                    logger.success("✅ Авторизация успешна (одношаговая форма)!")
                    await self.save_session()
                    return True

                await self._save_debug_screenshot("login_no_password")
                raise LoginError("Не удалось найти поле пароля")

            await self._page.wait_for_timeout(1000)

            # ── ШАГ 4: Нажимаем кнопку входа ──
            submit_selectors = [
                'button[type="submit"]',
                'button:has-text("Log In")',
                'button:has-text("Sign In")',
                'button:has-text("Login")',
                'button:has-text("Войти")',
            ]

            submitted = False
            for target in all_targets:
                for sel in submit_selectors:
                    try:
                        btn = target.locator(sel).first
                        if await btn.is_visible(timeout=2000):
                            await btn.click()
                            submitted = True
                            frame_name = getattr(target, 'name', 'main') or 'main'
                            logger.info("Кнопка входа нажата: {} (frame: {})", sel, frame_name)
                            break
                    except Exception:
                        continue
                if submitted:
                    break

            if not submitted:
                logger.warning("Кнопка входа не найдена, возможно форма отправлена автоматически")

            # ── ШАГ 5: Ждём завершения авторизации ──
            logger.info("Ожидаем завершения авторизации (до 20 сек)...")
            for _ in range(20):
                await self._page.wait_for_timeout(1000)
                if await self.check_logged_in():
                    logger.success("✅ Авторизация успешна!")
                    await self.save_session()
                    return True

            await self._save_debug_screenshot("login_timeout")
            raise LoginError("Таймаут авторизации — select_cookie не стал 1")

        except LoginError:
            raise
        except Exception as e:
            logger.error("Ошибка авторизации: {}", str(e))
            await self._save_debug_screenshot("login_error")
            raise LoginError(f"Ошибка авторизации: {e}") from e

    async def _save_debug_screenshot(self, name: str) -> None:
        """Сохранить скриншот для отладки."""
        try:
            if self._page:
                screenshot_path = Path("data") / f"{name}.png"
                screenshot_path.parent.mkdir(parents=True, exist_ok=True)
                await self._page.screenshot(path=str(screenshot_path))
                logger.info("Скриншот: {}", screenshot_path)
        except Exception as e:
            logger.warning("Не удалось сохранить скриншот: {}", e)

    # ── Cookie extraction ─────────────────────────────────────

    async def get_cookies_dict(self) -> dict[str, str]:
        """Получить куки как dict для httpx."""
        if self._context is None:
            return {}

        cookies = await self._context.cookies("https://www.midasbuy.com")
        return {c["name"]: c["value"] for c in cookies}

    async def get_page(self) -> Page:
        """Получить текущую страницу (для fallback-активации через браузер)."""
        await self._ensure_context()
        return self._page

    @property
    def is_logged_in(self) -> bool:
        return self._is_logged_in
