from __future__ import annotations

from typing import Any

from .label_resolvers import MessageRenderContext, resolve_label


def _extract_label_key(node: dict[str, Any]) -> str:
    raw_key = node.get("labelKey")
    if isinstance(raw_key, str):
        return raw_key

    fallback_key = node.get("label_key")
    if isinstance(fallback_key, str):
        return fallback_key

    legacy_key = node.get("id")
    if isinstance(legacy_key, str):
        return legacy_key

    return ""


def _render_node(node: Any, context: MessageRenderContext, channel: str) -> str:
    if isinstance(node, str):
        return node

    if isinstance(node, list):
        return "".join(_render_node(child, context, channel) for child in node)

    if not isinstance(node, dict):
        return ""

    node_type = node.get("type")
    if node_type == "label":
        label_key = _extract_label_key(node)
        if not label_key:
            return ""
        return resolve_label(label_key, context, channel)

    text_value = node.get("text")
    if isinstance(text_value, str):
        return text_value

    children = node.get("children")
    if isinstance(children, list):
        return "".join(_render_node(child, context, channel) for child in children)

    return ""


def build_message_body(template_value: Any, context: MessageRenderContext, channel: str) -> str:
    if not isinstance(template_value, list):
        return ""

    rendered_blocks = [_render_node(block, context, channel) for block in template_value]

    return "\n".join(rendered_blocks).strip("\n")
