from dataclasses import dataclass
from datetime import datetime

from app.domain.visit import VisitType


@dataclass(frozen=True, slots=True)
class VisitNotification:
    recipient_email: str
    brother_name: str
    visit_type: VisitType
    scheduled_at: datetime
    duration_minutes: int
    location: str