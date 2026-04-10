from Delivery_app_BK.services.infra.tasks.order.send_sms import send_sms

from ._actions import run_action



def send_sms_on_order_confirmed(order_event) -> None:
    run_action(order_event, "order_confirmed_sms", send_sms)


def send_sms_on_order_created(order_event) -> None:
    run_action(order_event, "order_created_sms", send_sms)


def send_sms_on_order_preparing(order_event) -> None:
    run_action(order_event, "order_preparing_sms", send_sms)


def send_sms_on_order_ready(order_event) -> None:
    run_action(order_event, "order_ready_sms", send_sms)


def send_sms_on_order_delivery_window_rescheduled_by_user(order_event) -> None:
    run_action(order_event, "order_delivery_window_rescheduled_by_user_sms", send_sms)


def send_sms_on_order_delivery_plan_changed(order_event) -> None:
    run_action(order_event, "order_delivery_plan_changed_sms", send_sms)


def send_sms_on_order_delivery_rescheduled(order_event) -> None:
    run_action(order_event, "order_delivery_rescheduled_sms", send_sms)



def send_sms_on_order_cancelled(order_event) -> None:
    run_action(order_event, "order_cancelled_sms", send_sms)


def send_sms_on_order_completed(order_event) -> None:
    run_action(order_event, "order_completed_sms", send_sms)


def send_sms_on_order_processing(order_event) -> None:
    run_action(order_event, "order_processing_sms", send_sms)


def send_sms_on_order_fail(order_event) -> None:
    run_action(order_event, "order_fail_sms", send_sms)


def send_sms_on_client_form_link_sent(order_event) -> None:
    run_action(order_event, "client_form_link_sent_sms", send_sms)
