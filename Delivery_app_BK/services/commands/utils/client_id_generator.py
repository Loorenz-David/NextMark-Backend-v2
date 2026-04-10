from __future__ import annotations

from contextvars import ContextVar, Token
from uuid import uuid4


_CLIENT_ID_NAMESPACE: ContextVar[str | None] = ContextVar(
    "client_id_namespace",
    default=None,
)


def generate_client_id(label=None):
    uui_id = uuid4().hex

    if label:
        return apply_client_id_namespace(f"{label}_{uui_id}")

    return apply_client_id_namespace(uui_id)


def get_client_id_namespace() -> str | None:
    return _CLIENT_ID_NAMESPACE.get()


def set_client_id_namespace(namespace: str | None) -> Token:
    normalized = _normalize_namespace(namespace)
    return _CLIENT_ID_NAMESPACE.set(normalized)


def reset_client_id_namespace(token: Token) -> None:
    _CLIENT_ID_NAMESPACE.reset(token)


def apply_client_id_namespace(client_id: str) -> str:
    namespace = get_client_id_namespace()
    if not namespace:
        return client_id

    normalized = str(client_id).strip()
    if normalized.startswith(namespace):
        return normalized
    return f"{namespace}{normalized}"


def _normalize_namespace(namespace: str | None) -> str | None:
    if namespace is None:
        return None

    normalized = str(namespace).strip()
    if not normalized:
        return None
    return normalized
