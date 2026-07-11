"""
Обработчик команды /status — показывает последние купоны пользователя.
"""
from telegram import Update
from telegram.ext import ContextTypes

from database.session import async_session
from database import crud


# Эмодзи для статусов БД
_STATUS_EMOJI = {
    "pending": "⏳",
    "processing": "🔄",
    "success": "✅",
    "failed": "❌",
    "duplicate": "♻️",
    "expired": "⏰",
    "invalid": "🚫",
}


async def status_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать последние купоны пользователя."""
    user = update.effective_user
    if not user:
        return

    async with async_session() as session:
        coupons = await crud.get_user_coupons(session, user.id, limit=10)

    if not coupons:
        await update.message.reply_text(
            "📭 У вас ещё нет купонов.\n"
            "Отправьте мне купон-код для активации!"
        )
        return

    lines = ["📋 *Ваши последние купоны:*\n"]
    for c in coupons:
        emoji = _STATUS_EMOJI.get(c.status, "❓")
        dt = c.submitted_at.strftime("%d.%m %H:%M") if c.submitted_at else "—"
        error = f"\n   └ _{c.error_msg}_" if c.error_msg else ""
        lines.append(
            f"{emoji} `{c.code}` — *{c.status}* ({dt}){error}"
        )

    await update.message.reply_text(
        "\n".join(lines),
        parse_mode="Markdown",
    )


async def stats_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Показать общую статистику (только для админа)."""
    from config.settings import settings

    user = update.effective_user
    if not user:
        return

    # Проверка прав администратора (по user_id или username)
    admin_id = settings.admin_chat_id
    is_admin = (
        str(user.id) == str(admin_id)
        or (user.username and user.username.lower() == admin_id.lower())
    )
    if not is_admin:
        await update.message.reply_text("🚫 Эта команда доступна только администратору.")
        return

    async with async_session() as session:
        stats = await crud.get_stats(session)

    await update.message.reply_text(
        f"📊 *Статистика бота*\n\n"
        f"👥 Пользователей: *{stats['total_users']}*\n"
        f"📦 Всего купонов: *{stats['total_coupons']}*\n"
        f"✅ Успешных: *{stats['success']}*\n"
        f"❌ Неудачных: *{stats['failed']}*\n"
        f"⏳ В очереди: *{stats['pending']}*",
        parse_mode="Markdown",
    )
