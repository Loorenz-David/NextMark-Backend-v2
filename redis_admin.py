from __future__ import annotations

import argparse
import json
import os
from typing import Callable

from Delivery_app_BK import create_app
from Delivery_app_BK.services.infra.events.requeue import (
    replay_app_event,
    replay_delivery_plan_event,
    replay_order_event,
    requeue_delivery_plan_action,
    requeue_order_action,
)
from Delivery_app_BK.services.infra.jobs.debug import get_queue_summary, list_failed_jobs


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Redis and async backbone admin helpers.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("summary", help="Show queue counts.")

    failed_parser = subparsers.add_parser("failed-jobs", help="List failed RQ jobs.")
    failed_parser.add_argument(
        "--queue",
        choices=["events", "messaging", "realtime", "default"],
        default=None,
        help="Filter to a single queue.",
    )
    failed_parser.add_argument("--limit", type=int, default=20, help="Maximum jobs to show.")

    replay_order_parser = subparsers.add_parser("replay-order-event", help="Replay an order event row.")
    replay_order_parser.add_argument("--id", type=int, required=True)

    replay_plan_parser = subparsers.add_parser(
        "replay-plan-event",
        help="Replay a delivery-plan event row.",
    )
    replay_plan_parser.add_argument("--id", type=int, required=True)

    replay_app_parser = subparsers.add_parser("replay-app-event", help="Replay an app outbox event row.")
    replay_app_parser.add_argument("--id", type=int, required=True)

    requeue_order_parser = subparsers.add_parser(
        "requeue-order-action",
        help="Requeue a failed/pending order action row.",
    )
    requeue_order_parser.add_argument("--id", type=int, required=True)

    requeue_plan_parser = subparsers.add_parser(
        "requeue-plan-action",
        help="Requeue a failed/pending delivery-plan action row.",
    )
    requeue_plan_parser.add_argument("--id", type=int, required=True)

    return parser


def _print_json(payload) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def _run_bool_action(action: Callable[[int], bool], record_id: int, label: str) -> int:
    success = action(record_id)
    _print_json({"ok": success, "id": record_id, "action": label})
    return 0 if success else 1


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    config_name = os.environ.get("APP_ENV", "development")
    app = create_app(config_name)

    with app.app_context():
        if args.command == "summary":
            _print_json({"queues": get_queue_summary()})
            return 0

        if args.command == "failed-jobs":
            _print_json(
                {
                    "queue": args.queue,
                    "jobs": list_failed_jobs(queue_key=args.queue, limit=args.limit),
                }
            )
            return 0

        if args.command == "replay-order-event":
            return _run_bool_action(replay_order_event, args.id, args.command)

        if args.command == "replay-plan-event":
            return _run_bool_action(replay_delivery_plan_event, args.id, args.command)

        if args.command == "replay-app-event":
            return _run_bool_action(replay_app_event, args.id, args.command)

        if args.command == "requeue-order-action":
            return _run_bool_action(requeue_order_action, args.id, args.command)

        if args.command == "requeue-plan-action":
            return _run_bool_action(requeue_delivery_plan_action, args.id, args.command)

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
