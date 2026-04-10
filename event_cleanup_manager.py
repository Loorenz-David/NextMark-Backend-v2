#!/usr/bin/env python
"""Management script for event cleanup operations.

Usage:
    python event_cleanup_manager.py cleanup [--retention-days 30]
    python event_cleanup_manager.py stats
"""

import os
import sys
from argparse import ArgumentParser

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from Delivery_app_BK import create_app
from Delivery_app_BK.services.infra.events.cleanup import cleanup_old_events, get_event_table_stats


def main():
    parser = ArgumentParser(description="Manage event database cleanup")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # Cleanup subcommand
    cleanup_parser = subparsers.add_parser("cleanup", help="Clean up old events")
    cleanup_parser.add_argument(
        "--retention-days",
        type=int,
        default=30,
        help="Number of days to retain events (default: 30)"
    )
    
    # Stats subcommand
    stats_parser = subparsers.add_parser("stats", help="Get event table statistics")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    config_name = os.environ.get("APP_ENV", "development")
    app = create_app(config_name)
    
    with app.app_context():
        if args.command == "cleanup":
            print(f"Cleaning up events older than {args.retention_days} days...")
            stats = cleanup_old_events(retention_days=args.retention_days)
            print("\nCleanup completed:")
            for key, count in stats.items():
                if key != "total_deleted":
                    print(f"  {key}: {count}")
            print(f"\nTotal deleted: {stats['total_deleted']} events")
        
        elif args.command == "stats":
            print("Event table statistics:")
            stats = get_event_table_stats()
            for table_name, info in stats.items():
                print(f"\n{table_name}:")
                if "error" in info:
                    print(f"  Error: {info['error']}")
                else:
                    print(f"  Total events: {info['count']}")
                    if info['oldest']:
                        print(f"  Oldest event: {info['oldest']}")


if __name__ == "__main__":
    main()
