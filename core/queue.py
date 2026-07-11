"""
Очередь задач на активацию купонов.
Обрабатывает купоны последовательно с задержкой и retry-логикой.
"""
import asyncio
from datetime import datetime

from loguru import logger

from config.settings import settings
from database.models import CouponStatus
from database import crud
from database.session import async_session
from activator.midasbuy import MidasBuyActivator, RedeemResult


# Маппинг RedeemResult → CouponStatus
_RESULT_TO_STATUS = {
    RedeemResult.SUCCESS: CouponStatus.SUCCESS,
    RedeemResult.INVALID: CouponStatus.INVALID,
    RedeemResult.EXPIRED: CouponStatus.EXPIRED,
    RedeemResult.ALREADY_USED: CouponStatus.DUPLICATE,
    RedeemResult.TIMEOUT: CouponStatus.FAILED,
    RedeemResult.FLAGGED: CouponStatus.FAILED,
    RedeemResult.ERROR: CouponStatus.FAILED,
    RedeemResult.SESSION_EXPIRED: CouponStatus.FAILED,
    RedeemResult.RATE_LIMITED: CouponStatus.PENDING,  # Retry later
}


class CouponQueue:
    """
    Асинхронная очередь для обработки купонов.
    Принимает купоны и обрабатывает их по одному.
    """

    def __init__(self, activator: MidasBuyActivator) -> None:
        self._activator = activator
        self._queue: asyncio.Queue[int] = asyncio.Queue()
        self._running = False
        self._worker_task: asyncio.Task | None = None
        self._callbacks: dict[int, asyncio.Future] = {}

    async def start(self) -> None:
        """Запустить обработчик очереди."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker())
        logger.info("Очередь купонов запущена")

    async def stop(self) -> None:
        """Остановить обработчик очереди."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
            self._worker_task = None
        logger.info("Очередь купонов остановлена")

    async def submit(self, coupon_id: int) -> asyncio.Future:
        """
        Добавить купон в очередь на обработку.

        Returns:
            Future, который разрешится когда купон будет обработан.
        """
        future = asyncio.get_event_loop().create_future()
        self._callbacks[coupon_id] = future
        await self._queue.put(coupon_id)
        logger.info("Купон #{} добавлен в очередь (размер: {})", coupon_id, self._queue.qsize())
        return future

    async def _worker(self) -> None:
        """Основной цикл обработки очереди."""
        logger.info("Worker очереди запущен")

        while self._running:
            try:
                coupon_id = await asyncio.wait_for(
                    self._queue.get(), timeout=5.0
                )
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            try:
                await self._process_coupon(coupon_id)
            except Exception as e:
                logger.error("Ошибка обработки купона #{}: {}", coupon_id, e)
                # Уведомляем callback об ошибке
                if coupon_id in self._callbacks:
                    future = self._callbacks.pop(coupon_id)
                    if not future.done():
                        future.set_exception(e)

            # Задержка между запросами
            await asyncio.sleep(settings.request_delay_seconds)

    async def _process_coupon(self, coupon_id: int) -> None:
        """Обработать один купон с retry-логикой."""
        async with async_session() as session:
            coupon = await crud.get_coupon_by_id(session, coupon_id)
            if coupon is None:
                logger.warning("Купон #{} не найден в БД", coupon_id)
                return

            # Помечаем как processing
            await crud.update_coupon_status(
                session, coupon_id, CouponStatus.PROCESSING
            )

            code = coupon.code
            attempt = coupon.attempts + 1

        # Retry loop
        last_result = None
        for retry in range(settings.max_retries):
            current_attempt = attempt + retry
            logger.info(
                "Попытка {}/{} для купона #{} ({})",
                retry + 1, settings.max_retries, coupon_id, code,
            )

            result = await self._activator.activate_coupon(code)
            last_result = result

            # Логируем попытку
            async with async_session() as session:
                await crud.create_activation_log(
                    session,
                    coupon_id=coupon_id,
                    attempt=current_attempt,
                    result_text=f"{result.result.value}: {result.message}",
                )

            # Определяем, нужен ли retry
            if result.result == RedeemResult.SUCCESS:
                logger.success("✅ Купон #{} ({}) активирован!", coupon_id, code)
                break
            elif result.result == RedeemResult.RATE_LIMITED:
                logger.warning("Rate limited, ждём {} сек...", settings.retry_delay_seconds * 2)
                await asyncio.sleep(settings.retry_delay_seconds * 2)
                continue
            elif result.result in (
                RedeemResult.INVALID,
                RedeemResult.EXPIRED,
                RedeemResult.ALREADY_USED,
            ):
                # Не retryable
                logger.warning("Купон #{} ({}): {} — retry не поможет", coupon_id, code, result.result.value)
                break
            else:
                # Retryable ошибки (timeout, error, flagged)
                if retry < settings.max_retries - 1:
                    logger.info("Retry через {} сек...", settings.retry_delay_seconds)
                    await asyncio.sleep(settings.retry_delay_seconds)
                continue

        # Обновляем статус в БД
        if last_result:
            final_status = _RESULT_TO_STATUS.get(
                last_result.result, CouponStatus.FAILED
            )
            async with async_session() as session:
                await crud.update_coupon_status(
                    session,
                    coupon_id,
                    final_status,
                    error_msg=last_result.message if final_status != CouponStatus.SUCCESS else None,
                )

        # Уведомляем callback
        if coupon_id in self._callbacks:
            future = self._callbacks.pop(coupon_id)
            if not future.done():
                future.set_result(last_result)
