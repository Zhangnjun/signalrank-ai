from __future__ import annotations

import json
import os
from pathlib import Path

from ai_hotspot_monitor.models import Source


def load_sources(path: str | Path) -> list[Source]:
    config_path = Path(path).expanduser().resolve()
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    raw_sources = payload.get("sources", [])
    sources = [_parse_source(item) for item in raw_sources if item.get("enabled", True)]
    if not sources:
        raise ValueError(f"No enabled sources configured in {config_path}")
    return sources


def _parse_source(item: dict) -> Source:
    metadata = {
        key: _resolve_env(value)
        for key, value in item.items()
        if key
        not in {
            "name",
            "url",
            "kind",
            "authority_weight",
            "enabled",
            "article_limit",
            "headers",
            "tags",
        }
    }
    headers = {
        key: _resolve_env(value)
        for key, value in item.get("headers", {}).items()
    }
    return Source(
        name=item["name"],
        url=item["url"],
        kind=item.get("kind", "rss"),
        authority_weight=float(item.get("authority_weight", 0.7)),
        enabled=bool(item.get("enabled", True)),
        article_limit=item.get("article_limit"),
        headers=headers,
        tags=list(item.get("tags", [])),
        metadata=metadata,
    )


def _resolve_env(value):
    if isinstance(value, str) and value.startswith("$") and len(value) > 1:
        return os.getenv(value[1:], "")
    if isinstance(value, list):
        return [_resolve_env(item) for item in value]
    if isinstance(value, dict):
        return {key: _resolve_env(item) for key, item in value.items()}
    return value
