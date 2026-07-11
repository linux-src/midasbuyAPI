"""
Rate limiting middleware для Telegram бота.
"""
from datetime import datetime, timedelta
from collections import defaultdict

from telegram import Update
from telegram.ext import ContextTypes

from config.settings import settings


class RateLimiter:
    """
    In-memory rate limiter для быстрой проверки.
    БД rate limit проверяется в coupon handler отдельно.
    """

    def __init__(
        self,
        max_messages: int = 20,
        period_seconds: int = 60,
    ) -> None:
        self.max_messages = max_messages
        self.period_seconds = period_seconds
        self._timestamps: dict[int, list[datetime]] = defaultdict(list)

    def is_limited(self, user_id: int) -> bool:
        """Проверить, превышен ли лимит сообщений для пользователя."""
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.period_seconds)

        # Очищаем старые записи
        self._timestamps[user_id] = [
            ts for ts in self._timestamps[user_id] if ts > cutoff
        ]

        if len(self._timestamps[user_id]) >= self.max_messages:
            return True

        self._timestamps[user_id].append(now)
        return False

    def cleanup(self) -> None:
        """Очистить устаревшие записи для экономии памяти."""
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.period_seconds * 2)

        expired_users = []
        for user_id, timestamps in self._timestamps.items():
            self._timestamps[user_id] = [ts for ts in timestamps if ts > cutoff]
            if not self._timestamps[user_id]:
                expired_users.append(user_id)

        for user_id in expired_users:
            del self._timestamps[user_id]


# Глобальный rate limiter
rate_limiter = RateLimiter(max_messages=20, period_seconds=60)
