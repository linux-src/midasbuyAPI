"""
Обработчик приёма и активации купонов через Telegram.
"""
import asyncio
import re
from datetime import datetime, timedelta

from loguru import logger
from telegram import Update
from telegram.ext import ContextTypes

from config.settings import settings
from database.session import async_session
from database import crud
from database.models import CouponStatus
from activator.midasbuy import ActivationResult, RedeemResult


# Regex для валидации купон-кода
COUPON_PATTERN = re.compile(r"^[A-Za-z0-9\-_]{4,50}$")

# Эмодзи для статусов
STATUS_EMOJI = {
    RedeemResult.SUCCESS: "✅",
    RedeemResult.INVALID: "🚫",
    RedeemResult.EXPIRED: "⏰",
    RedeemResult.ALREADY_USED: "♻️",
    RedeemResult.TIMEOUT: "⏱️",
    RedeemResult.FLAGGED: "🔍",
    RedeemResult.ERROR: "❌",
    RedeemResult.SESSION_EXPIRED: "🔒",
    RedeemResult.RATE_LIMITED: "⏳",
}


async def coupon_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Обработчик текстовых сообщений — принимает купон-коды.
    """
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    if not user:
        return

    text = update.message.text.strip()

    # Пропускаем команды
    if text.startswith("/"):
        return

    # Валидация формата
    if not COUPON_PATTERN.match(text):
        await update.message.reply_text(
            "⚠️ *Неверный формат купона.*\n\n"
            "Купон должен содержать только буквы (A-Z), цифры (0-9), "
            "дефис (-) и подчёркивание (\_).\n"
            "Длина: от 4 до 50 символов.",
            parse_mode="Markdown",
        )
        return

    coupon_code = text.upper()

    async with async_session() as session:
        # Проверка бана
        if await crud.is_user_banned(session, user.id):
            await update.message.reply_text(
                "🚫 Ваш аккаунт заблокирован. Обратитесь к администратору."
            )
            return

        # Rate limiting
        since = datetime.utcnow() - timedelta(
            seconds=settings.rate_limit_period_seconds
        )
        count = await crud.count_user_coupons_in_period(session, user.id, since)

        if count >= settings.rate_limit_max_coupons:
            await update.message.reply_text(
                f"⏳ *Лимит превышен.*\n\n"
                f"Вы отправили {count}/{settings.rate_limit_max_coupons} "
                f"купонов за последний час.\n"
                f"Подождите немного и попробуйте снова.",
                parse_mode="Markdown",
            )
            return

        # Регистрируем пользователя
        await crud.get_or_create_user(
            session,
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
        )

        # Создаём запись купона
        coupon = await crud.create_coupon(session, coupon_code, user.id)

    logger.info(
        "Получен купон {} от @{} (user_id={}), coupon_id={}",
        coupon_code, user.username, user.id, coupon.id,
    )

    # Отправляем подтверждение
    msg = await update.message.reply_text(
        f"📥 Купон `{coupon_code}` принят!\n\n"
        f"⏳ Обрабатывается... (#{coupon.id})",
        parse_mode="Markdown",
    )

    # Добавляем в очередь
    coupon_queue = context.bot_data.get("coupon_queue")
    if coupon_queue is None:
        await msg.edit_text(
            f"❌ Сервис активации не запущен. Купон `{coupon_code}` сохранён и будет обработан позже.",
            parse_mode="Markdown",
        )
        return

    try:
        future = await coupon_queue.submit(coupon.id)
        # Ждём результат (максимум 120 секунд)
        result: ActivationResult = await asyncio.wait_for(future, timeout=120)

        emoji = STATUS_EMOJI.get(result.result, "❓")
        status_text = result.result.value

        await msg.edit_text(
            f"{emoji} *Купон* `{coupon_code}`\n\n"
            f"*Статус:* {status_text}\n"
            f"*Сообщение:* {result.message}",
            parse_mode="Markdown",
        )

    except asyncio.TimeoutError:
        await msg.edit_text(
            f"⏱️ Обработка купона `{coupon_code}` заняла слишком долго.\n"
            f"Результат будет доступен по команде /status",
            parse_mode="Markdown",
        )

    except Exception as e:
        logger.error("Ошибка при обработке купона {}: {}", coupon_code, e)
        await msg.edit_text(
            f"❌ Ошибка при обработке купона `{coupon_code}`:\n{e}",
            parse_mode="Markdown",
        )


