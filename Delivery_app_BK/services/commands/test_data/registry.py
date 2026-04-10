from __future__ import annotations


class RefResolutionError(Exception):
    """Raised when a $ref cannot be resolved to a DB ID."""


class Registry:
    def __init__(self) -> None:
        self._forward: dict[str, int] = {}
        self._reverse: dict[str, dict[int, str]] = {}

    def register(self, sid: str, db_id: int, entity_key: str | None = None) -> None:
        """Register a symbolic ID against a DB integer ID."""
        if not isinstance(sid, str) or not sid:
            raise ValueError(f"sid must be a non-empty string, got {sid!r}")
        if not isinstance(db_id, int) or db_id <= 0:
            raise ValueError(f"db_id must be a positive integer, got {db_id!r}")

        self._forward[sid] = db_id
        if entity_key:
            self._reverse.setdefault(entity_key, {})[db_id] = sid

    def resolve(self, sid: str) -> int:
        """Resolve a symbolic ID to its DB integer ID."""
        if sid not in self._forward:
            raise RefResolutionError(
                f"Cannot resolve ref ${sid!r}: no entity with that $id has been registered. "
                "Check that the referenced entity appears earlier in the payload and that "
                "its $id matches exactly."
            )
        return self._forward[sid]

    def reverse_lookup(self, entity_key: str, db_id: int) -> str:
        """Look up a symbolic ID by entity key and DB ID."""
        entity_map = self._reverse.get(entity_key, {})
        if db_id not in entity_map:
            raise RefResolutionError(
                f"No $id registered for {entity_key} with DB id={db_id}."
            )
        return entity_map[db_id]

    def is_registered(self, sid: str) -> bool:
        return sid in self._forward


__all__ = ["Registry", "RefResolutionError"]
