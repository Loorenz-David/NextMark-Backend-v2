from datetime import datetime, timezone

from Delivery_app_BK.models import db, RoutePlanEvent, RoutePlanEventAction
from Delivery_app_BK.services.infra.events.action_dispatch import enqueue_route_plan_action
from Delivery_app_BK.services.infra.messaging.action_scheduling import resolve_route_plan_action_schedule


def _upsert_action(
    plan_event_id: int,
    action_name: str,
    team_id: int | None,
    *,
    resolved_schedule,
) -> RoutePlanEventAction:
    action = (
        db.session.query(RoutePlanEventAction)
        .filter(
            RoutePlanEventAction.event_id == plan_event_id,
            RoutePlanEventAction.action_name == action_name,
        )
        .first()
    )

    if action is None:
        action = RoutePlanEventAction(
            event_id=plan_event_id,
            action_name=action_name,
            team_id=team_id,
            status=(
                RoutePlanEventAction.STATUS_SKIPPED
                if resolved_schedule.skip_reason
                else RoutePlanEventAction.STATUS_PENDING
            ),
            attempts=0,
            last_error=resolved_schedule.skip_reason,
            scheduled_for=resolved_schedule.scheduled_for,
            schedule_anchor_type=resolved_schedule.schedule_anchor_type,
            schedule_anchor_at=resolved_schedule.schedule_anchor_at,
            processed_at=datetime.now(timezone.utc) if resolved_schedule.skip_reason else None,
        )
        db.session.add(action)
        db.session.flush()
        return action

    action.status = (
        RoutePlanEventAction.STATUS_SKIPPED
        if resolved_schedule.skip_reason
        else RoutePlanEventAction.STATUS_PENDING
    )
    action.last_error = resolved_schedule.skip_reason
    action.scheduled_for = resolved_schedule.scheduled_for
    action.schedule_anchor_type = resolved_schedule.schedule_anchor_type
    action.schedule_anchor_at = resolved_schedule.schedule_anchor_at
    action.processed_at = datetime.now(timezone.utc) if resolved_schedule.skip_reason else None
    action.updated_at = datetime.now(timezone.utc)
    db.session.flush()
    return action


def run_action(plan_event:RoutePlanEvent, action_name: str, _runner) -> None:
  
    team_id = getattr(plan_event, "team_id", None)
    resolved_schedule = resolve_route_plan_action_schedule(plan_event, action_name)
    if resolved_schedule is None:
        return

    action = _upsert_action(
        plan_event.id,
        action_name,
        team_id,
        resolved_schedule=resolved_schedule,
    )
    db.session.commit()
    if action.status == RoutePlanEventAction.STATUS_SKIPPED:
        return

    try:
        enqueue_route_plan_action(action)
    except Exception as exc:
        failed_action = db.session.get(RoutePlanEventAction, action.id)
        if failed_action is None:
            return
        failed_action.attempts = (failed_action.attempts or 0) + 1
        failed_action.status = RoutePlanEventAction.STATUS_FAILED
        failed_action.last_error = str(exc)
        db.session.commit()
