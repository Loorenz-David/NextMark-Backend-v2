from Delivery_app_BK.services.infra.tasks.order.send_email import send_email

from ._actions import run_action



def send_email_on_order_created(order_event) -> None:
    run_action(order_event, "order_created_email", send_email)


def send_email_on_order_confirmed(order_event) -> None:
    run_action(order_event, "order_confirmed_email", send_email)



def send_email_on_order_preparing(order_event) -> None:
    run_action(order_event, "order_preparing_email", send_email)


def send_email_on_order_ready(order_event) -> None:
    run_action(order_event, "order_ready_email", send_email)


def send_email_on_order_delivery_window_rescheduled_by_user(order_event) -> None:
    run_action(order_event, "order_delivery_window_rescheduled_by_user_email", send_email)


def send_email_on_order_delivery_plan_changed(order_event) -> None:
    run_action(order_event, "order_delivery_plan_changed_email", send_email)


def send_email_on_order_delivery_rescheduled(order_event) -> None:
    run_action(order_event, "order_delivery_rescheduled_email", send_email)



def send_email_on_order_cancelled(order_event) -> None:
    run_action(order_event, "order_cancelled_email", send_email)


def send_email_on_order_processing(order_event) -> None:
    run_action(order_event, "order_processing_email", send_email)


def send_email_on_order_completed(order_event) -> None:
    run_action(order_event, "order_completed_email", send_email)


def send_email_on_order_fail(order_event) -> None:
    run_action(order_event, "order_fail_email", send_email)


def send_email_on_client_form_link_sent(order_event) -> None:
    run_action(order_event, "client_form_link_sent_email", send_email)
