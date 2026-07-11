"""
Обработчики Telegram бота: /start, /help.
"""
from loguru import logger
from telegram import Update
from telegram.ext import ContextTypes

from database.session import async_session
from database import crud


START_TEXT = """
🎮 *MidasBuy Coupon Bot*

Добро пожаловать! Этот бот автоматически активирует купоны на midasbuy.com.

📋 *Как использовать:*
1. Отправьте мне купон-код
2. Бот автоматически активирует его
3. Вы получите результат

📌 *Команды:*
/start — Начать
/help — Помощь
/status — Последние купоны
/stats — Статистика (админ)

⚠️ *Лимит:* 5 купонов в час
"""

HELP_TEXT = """
❓ *Помощь*

Просто отправьте мне *купон-код* текстовым сообщением.

*Форматы купонов:*
• Только латинские буквы и цифры
• Длина: от 4 до 50 символов
• Без пробелов

*Статусы:*
✅ `success` — Купон активирован
❌ `failed` — Ошибка активации
⏳ `pending` — В очереди
🔄 `processing` — Обрабатывается
♻️ `duplicate` — Уже использован
⏰ `expired` — Срок истёк
🚫 `invalid` — Невалидный

Если купон не сработал, бот сделает до 3 попыток.
"""


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /start."""
    user = update.effective_user
    if not user:
        return

    logger.info(
        "/start от @{} (user_id={}, chat_id={})",
        user.username, user.id, update.effective_chat.id,
    )

    # Регистрируем пользователя в БД
    async with async_session() as session:
        await crud.get_or_create_user(
            session,
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
        )

    await update.message.reply_text(
        START_TEXT,
        parse_mode="Markdown",
    )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Обработчик команды /help."""
    await update.message.reply_text(
        HELP_TEXT,
        parse_mode="Markdown",
    )
