import asyncio
import logging

from app.infrastructure.visit_notification_dispatcher import VisitNotificationDispatcher


logger = logging.getLogger(__name__)


class VisitNotificationWorker:
    def __init__(
        self,
        dispatcher: VisitNotificationDispatcher,
        *,
        poll_interval_seconds: float = 30,
    ) -> None:
        self._dispatcher = dispatcher
        self._poll_interval_seconds = poll_interval_seconds

    async def run(self, stop_event: asyncio.Event) -> None:
        while not stop_event.is_set():
            try:
                await asyncio.wait_for(
                    stop_event.wait(),
                    timeout=self._poll_interval_seconds,
                )
            except TimeoutError:
                pass
            if stop_event.is_set():
                return
            try:
                await self._dispatcher.process_pending()
            except Exception as error:
                logger.error(
                    "Notification outbox polling failed",
                    extra={"error_type": type(error).__name__},
                )