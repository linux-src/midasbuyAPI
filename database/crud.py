"""
CRUD операции для работы с базой данных.
"""
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import ActivationLog, Coupon, CouponStatus, User


# ── Users ──────────────────────────────────────────────────────


async def get_or_create_user(
    session: AsyncSession,
    user_id: int,
    username: str | None = None,
    first_name: str | None = None,
) -> User:
    """Получить пользователя или создать нового."""
    result = await session.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None:
        user = User(id=user_id, username=username, first_name=first_name)
        session.add(user)
        await session.commit()
        await session.refresh(user)
    else:
        # Обновляем username если изменился
        if username and user.username != username:
            user.username = username
            await session.commit()

    return user


async def is_user_banned(session: AsyncSession, user_id: int) -> bool:
    """Проверить, забанен ли пользователь."""
    result = await session.execute(
        select(User.is_banned).where(User.id == user_id)
    )
    banned = result.scalar_one_or_none()
    return banned is True


# ── Coupons ────────────────────────────────────────────────────


async def create_coupon(
    session: AsyncSession,
    code: str,
    user_id: int,
) -> Coupon:
    """Создать запись купона."""
    coupon = Coupon(
        code=code,
        user_id=user_id,
        status=CouponStatus.PENDING.value,
    )
    session.add(coupon)
    await session.commit()
    await session.refresh(coupon)
    return coupon


async def get_coupon_by_id(session: AsyncSession, coupon_id: int) -> Coupon | None:
    """Получить купон по ID."""
    result = await session.execute(select(Coupon).where(Coupon.id == coupon_id))
    return result.scalar_one_or_none()


async def get_pending_coupons(session: AsyncSession) -> list[Coupon]:
    """Получить все купоны в статусе pending."""
    result = await session.execute(
        select(Coupon)
        .where(Coupon.status == CouponStatus.PENDING.value)
        .order_by(Coupon.submitted_at.asc())
    )
    return list(result.scalars().all())


async def update_coupon_status(
    session: AsyncSession,
    coupon_id: int,
    status: CouponStatus,
    error_msg: str | None = None,
) -> Coupon | None:
    """Обновить статус купона."""
    coupon = await get_coupon_by_id(session, coupon_id)
    if coupon is None:
        return None

    coupon.status = status.value
    coupon.attempts += 1

    if status == CouponStatus.SUCCESS:
        coupon.activated_at = datetime.utcnow()

    if error_msg:
        coupon.error_msg = error_msg

    await session.commit()
    await session.refresh(coupon)
    return coupon


async def get_user_coupons(
    session: AsyncSession,
    user_id: int,
    limit: int = 10,
) -> list[Coupon]:
    """Получить последние купоны пользователя."""
    result = await session.execute(
        select(Coupon)
        .where(Coupon.user_id == user_id)
        .order_by(Coupon.submitted_at.desc())
        .limit(limit)
    )
    return list(result.scalars().all())


async def count_user_coupons_in_period(
    session: AsyncSession,
    user_id: int,
    since: datetime,
) -> int:
    """Подсчёт купонов пользователя за период (для rate limiting)."""
    result = await session.execute(
        select(func.count(Coupon.id))
        .where(Coupon.user_id == user_id)
        .where(Coupon.submitted_at >= since)
    )
    return result.scalar_one()


# ── Activation Logs ────────────────────────────────────────────


async def create_activation_log(
    session: AsyncSession,
    coupon_id: int,
    attempt: int,
    result_text: str | None = None,
    screenshot: str | None = None,
) -> ActivationLog:
    """Создать запись лога активации."""
    log = ActivationLog(
        coupon_id=coupon_id,
        attempt=attempt,
        result=result_text,
        screenshot=screenshot,
    )
    session.add(log)
    await session.commit()
    await session.refresh(log)
    return log


async def get_stats(session: AsyncSession) -> dict:
    """Получить общую статистику."""
    total = await session.execute(select(func.count(Coupon.id)))
    success = await session.execute(
        select(func.count(Coupon.id))
        .where(Coupon.status == CouponStatus.SUCCESS.value)
    )
    failed = await session.execute(
        select(func.count(Coupon.id))
        .where(Coupon.status == CouponStatus.FAILED.value)
    )
    pending = await session.execute(
        select(func.count(Coupon.id))
        .where(Coupon.status == CouponStatus.PENDING.value)
    )
    users = await session.execute(select(func.count(User.id)))

    return {
        "total_coupons": total.scalar_one(),
        "success": success.scalar_one(),
        "failed": failed.scalar_one(),
        "pending": pending.scalar_one(),
        "total_users": users.scalar_one(),
    }
