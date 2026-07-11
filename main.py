"""
MidasBuy Coupon Bot — Точка входа.

Запускает Telegram бота и систему активации купонов.
"""
import asyncio
import sys
from pathlib import Path

from loguru import logger

# Настройка loguru
from config.settings import settings


def setup_logging() -> None:
    """Настройка системы логирования."""
    logger.remove()  # Удаляем дефолтный handler

    # Консольный вывод
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # Файловый лог
    log_path = Path(settings.log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)
    logger.add(
        str(log_path),
        level=settings.log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} | {message}",
        rotation="10 MB",
        retention="7 days",
        compression="zip",
    )


async def main() -> None:
    """Основная функция запуска."""
    setup_logging()
    logger.info("=" * 50)
    logger.info("🚀 MidasBuy Coupon Bot запускается...")
    logger.info("=" * 50)

    # Импорты после настройки логирования
    from telegram.ext import (
        ApplicationBuilder,
        CommandHandler,
        MessageHandler,
        filters,
    )

    from database.session import init_db
    from activator.browser import BrowserManager
    from activator.midasbuy import MidasBuyActivator
    from core.queue import CouponQueue
    from bot.handlers.start import start_handler, help_handler
    from bot.handlers.coupon import coupon_handler
    from bot.handlers.status import status_handler, stats_handler

    # ── 1. Инициализация БД ───────────────────────────────────
    logger.info("Инициализация базы данных...")
    await init_db()
    logger.info("✅ База данных готова")

    # ── 2. Инициализация активатора ───────────────────────────
    browser_manager = BrowserManager()
    activator = MidasBuyActivator(browser_manager)

    logger.info("Запуск активатора (логин на midasbuy.com)...")
    try:
        await activator.start()
        logger.info("✅ Активатор запущен, авторизация успешна")
    except Exception as e:
        logger.error("❌ Не удалось запустить активатор: {}", e)
        logger.warning("Бот будет работать, но активация купонов недоступна до перезапуска")

    # ── 3. Очередь купонов ────────────────────────────────────
    coupon_queue = CouponQueue(activator)
    await coupon_queue.start()
    logger.info("✅ Очередь купонов запущена")

    # ── 4. Telegram бот ───────────────────────────────────────
    logger.info("Запуск Telegram бота...")
    app = (
        ApplicationBuilder()
        .token(settings.telegram_bot_token)
        .connect_timeout(30.0)
        .read_timeout(30.0)
        .write_timeout(30.0)
        .pool_timeout(30.0)
        .build()
    )

    # Передаём очередь в bot_data для доступа из хэндлеров
    app.bot_data["coupon_queue"] = coupon_queue
    app.bot_data["activator"] = activator
    app.bot_data["browser_manager"] = browser_manager

    # Регистрируем обработчики
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("help", help_handler))
    app.add_handler(CommandHandler("status", status_handler))
    app.add_handler(CommandHandler("stats", stats_handler))

    # Все текстовые сообщения — как купоны
    app.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        coupon_handler,
    ))

    logger.info("✅ Бот готов к работе!")
    logger.info("Ожидание сообщений...")

    # Запускаем бота
    try:
        await app.initialize()
        await app.start()
        await app.updater.start_polling(drop_pending_updates=True)

        # Ждём бесконечно
        stop_event = asyncio.Event()
        await stop_event.wait()

    except KeyboardInterrupt:
        logger.info("Получен сигнал остановки...")
    finally:
        logger.info("Остановка бота...")
        try:
            await app.updater.stop()
            await app.stop()
            await app.shutdown()
        except Exception:
            pass

        await coupon_queue.stop()
        await activator.stop()
        logger.info("👋 Бот остановлен")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n👋 Завершение работы")
