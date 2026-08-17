from __future__ import annotations

from finreg.config import Config
from finreg.sources.base import Source

_REGISTRY: dict[str, Source] = {}


def register(source: Source) -> None:
    _REGISTRY[source.name] = source


def all_registered() -> dict[str, Source]:
    return dict(_REGISTRY)


def get_enabled_sources(config: Config) -> dict[str, Source]:
    enabled: dict[str, Source] = {}
    for name, source_config in config.sources.items():
        if source_config.enabled and name in _REGISTRY:
            enabled[name] = _REGISTRY[name]
    return enabled
