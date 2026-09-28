from app.domain.visit import Visit, VisitHistoryEntry, VisitStatus, VisitType
from app.infrastructure.models import VisitHistoryModel, VisitModel


class VisitFactory:
    @staticmethod
    def from_model(model: VisitModel, church_id) -> Visit:
        return Visit(
            id=model.id,
            brother_id=model.brother_id,
            leader_id=model.leader_id,
            church_id=church_id,
            created_by_id=model.created_by_id,
            visit_type=VisitType(model.visit_type),
            scheduled_at=model.scheduled_at,
            completed_at=model.completed_at,
            duration_minutes=model.duration_minutes,
            location=model.location,
            observations=model.observations,
            status=VisitStatus(model.status),
            cancellation_reason=model.cancellation_reason,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def history_from_model(model: VisitHistoryModel) -> VisitHistoryEntry:
        return VisitHistoryEntry(
            id=model.id,
            visit_id=model.visit_id,
            actor_id=model.actor_id,
            action=model.action,
            previous_status=(
                VisitStatus(model.previous_status) if model.previous_status is not None else None
            ),
            new_status=VisitStatus(model.new_status) if model.new_status is not None else None,
            previous_scheduled_at=model.previous_scheduled_at,
            new_scheduled_at=model.new_scheduled_at,
            previous_values=model.previous_values,
            new_values=model.new_values,
            reason=model.reason,
            created_at=model.created_at,
        )