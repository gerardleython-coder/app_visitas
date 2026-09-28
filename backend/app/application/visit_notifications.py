from typing import Protocol

from app.domain.notification import VisitNotification
from app.domain.visit import Visit


class VisitNotificationQueue(Protocol):
    async def enqueue_visit_created(self, visit: Visit) -> None: ...


class VisitEmailSender(Protocol):
    async def send_visit_created(self, notification: VisitNotification) -> None: ...