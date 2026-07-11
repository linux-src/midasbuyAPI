"""
Кастомные исключения для модуля активации купонов.
"""


class ActivatorError(Exception):
    """Базовое исключение активатора."""
    pass


class LoginError(ActivatorError):
    """Ошибка авторизации на сайте."""
    pass


class SessionExpiredError(ActivatorError):
    """Сессия истекла, требуется повторный логин."""
    pass


class CouponError(ActivatorError):
    """Базовая ошибка при работе с купонами."""
    pass


class CouponInvalidError(CouponError):
    """Купон невалидный."""
    pass


class CouponExpiredError(CouponError):
    """Купон истёк."""
    pass


class CouponAlreadyUsedError(CouponError):
    """Купон уже использован."""
    pass


class CouponTimeoutError(CouponError):
    """Таймаут при активации купона."""
    pass


class CouponFlaggedError(CouponError):
    """Запрос помечен для дополнительной проверки."""
    pass


class BrowserError(ActivatorError):
    """Ошибка работы с браузером."""
    pass


class RateLimitError(ActivatorError):
    """Превышен rate limit сайта."""
    pass
