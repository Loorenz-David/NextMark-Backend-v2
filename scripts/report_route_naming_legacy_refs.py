#!/usr/bin/env python3
"""Report legacy route-naming references for migration tracking.

This script is intentionally simple and grep-like so it can run in CI or local
workflows without extra dependencies.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from pathlib import Path
import re
import sys


ROOT = Path(__file__).resolve().parents[1]
SCAN_DIRS = [ROOT / "Delivery_app_BK", ROOT / "tests"]

# Keep focused on migration-critical legacy identifiers.
PATTERNS = {
    "delivery_plan token": re.compile(r"\bdelivery_plan\b"),
    "local_delivery_plan token": re.compile(r"\blocal_delivery_plan\b"),
    "delivery_plan_id key": re.compile(r"\bdelivery_plan_id\b"),
    "local_delivery_plan_id key": re.compile(r"\blocal_delivery_plan_id\b"),
}

EXCLUDE_DIR_NAMES = {
    ".git",
    "__pycache__",
    ".venv",
    "venv",
    "node_modules",
    "migrations",
}


def _iter_python_files() -> list[Path]:
    files: list[Path] = []
    for base in SCAN_DIRS:
        if not base.exists():
            continue
        for path in base.rglob("*.py"):
            if any(part in EXCLUDE_DIR_NAMES for part in path.parts):
                continue
            files.append(path)
    return sorted(files)


def main() -> int:
    files = _iter_python_files()
    if not files:
        print("No Python files found in scan scope.")
        return 1

    totals = Counter()
    per_file_hits: dict[Path, Counter[str]] = defaultdict(Counter)

    for file_path in files:
        try:
            content = file_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue

        for label, pattern in PATTERNS.items():
            count = len(pattern.findall(content))
            if count:
                totals[label] += count
                per_file_hits[file_path][label] += count

    print("Route naming legacy reference report")
    print(f"Repo root: {ROOT}")
    print(f"Files scanned: {len(files)}")
    print()

    print("Totals by pattern")
    for label in PATTERNS:
        print(f"- {label}: {totals.get(label, 0)}")
    print()

    if not per_file_hits:
        print("No legacy references found in scanned files.")
        return 0

    # Rank by total hits, then path.
    ranked = sorted(
        per_file_hits.items(),
        key=lambda item: (-sum(item[1].values()), str(item[0])),
    )

    print("Top files by legacy hit count")
    for file_path, counts in ranked[:25]:
        rel = file_path.relative_to(ROOT)
        total = sum(counts.values())
        details = ", ".join(f"{k}={v}" for k, v in sorted(counts.items()))
        print(f"- {rel}: total={total} ({details})")

    return 0


if __name__ == "__main__":
    sys.exit(main())
