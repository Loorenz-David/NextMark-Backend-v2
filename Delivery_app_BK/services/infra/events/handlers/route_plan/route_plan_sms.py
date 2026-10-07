from ._actions import run_action

def send_sms_on_route_plan_rescheduled(plan_event) -> None:
    run_action(plan_event, "plan_delivery_rescheduled_sms")
