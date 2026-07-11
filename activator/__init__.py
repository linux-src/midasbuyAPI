"""Activator package — модуль активации купонов на midasbuy.com."""
from activator.browser import BrowserManager
from activator.midasbuy import MidasBuyActivator, ActivationResult, RedeemResult
from activator.exceptions import (
    ActivatorError,
    LoginError,
    SessionExpiredError,
    CouponError,
    CouponInvalidError,
    CouponExpiredError,
    CouponAlreadyUsedError,
    BrowserError,
    RateLimitError,
)

__all__ = [
    "BrowserManager",
    "MidasBuyActivator",
    "ActivationResult",
    "RedeemResult",
    "ActivatorError",
    "LoginError",
    "SessionExpiredError",
    "CouponError",
    "CouponInvalidError",
    "CouponExpiredError",
    "CouponAlreadyUsedError",
    "BrowserError",
    "RateLimitError",
]
