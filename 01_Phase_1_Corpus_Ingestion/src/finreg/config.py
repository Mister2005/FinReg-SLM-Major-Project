from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from pathlib import Path

import yaml


class ConfigError(Exception):
    def __init__(self, field_name: str, detail: str) -> None:
        self.field_name = field_name
        super().__init__(f"{field_name}: {detail}")


@dataclass(frozen=True)
class DateWindow:
    start: str
    end: str | None


@dataclass(frozen=True)
class SourceDefaults:
    min_interval_seconds: float
    max_retries: int
    timeout_seconds: float
    max_failure_rate: float


@dataclass(frozen=True)
class SourceConfig:
    name: str
    enabled: bool
    host: str
    strategy: str
    min_interval_seconds: float


@dataclass(frozen=True)
class IdentityOverride:
    user_agent: str
    reason: str


@dataclass(frozen=True)
class Config:
    contact_email: str
    window: DateWindow
    defaults: SourceDefaults
    sources: dict[str, SourceConfig]
    sha256: str = field(compare=False)
    identity_overrides: dict[str, IdentityOverride] = field(default_factory=dict)


_REQUIRED_TOP_LEVEL = ("contact_email", "window", "defaults", "sources")
_REQUIRED_WINDOW = ("start",)
_REQUIRED_DEFAULTS = (
    "min_interval_seconds",
    "max_retries",
    "timeout_seconds",
    "max_failure_rate",
)
_REQUIRED_SOURCE = ("enabled", "host", "strategy")


def load_config(path: Path) -> Config:
    raw_bytes = path.read_bytes()
    sha256 = hashlib.sha256(raw_bytes).hexdigest()
    raw = yaml.safe_load(raw_bytes)

    if not isinstance(raw, dict):
        raise ConfigError("<root>", "config file must be a YAML mapping")

    for key in _REQUIRED_TOP_LEVEL:
        if key not in raw:
            raise ConfigError(key, "required top-level key is missing")

    contact_email = raw["contact_email"]
    if not isinstance(contact_email, str) or not contact_email.strip():
        raise ConfigError("contact_email", "must be a non-empty string")
    if contact_email == "REQUIRED — set before first run":
        raise ConfigError("contact_email", "placeholder value has not been replaced")

    window_raw = raw["window"]
    for key in _REQUIRED_WINDOW:
        if key not in window_raw:
            raise ConfigError(f"window.{key}", "required key is missing")
    window = DateWindow(start=window_raw["start"], end=window_raw.get("end"))

    defaults_raw = raw["defaults"]
    for key in _REQUIRED_DEFAULTS:
        if key not in defaults_raw:
            raise ConfigError(f"defaults.{key}", "required key is missing")
    defaults = SourceDefaults(
        min_interval_seconds=float(defaults_raw["min_interval_seconds"]),
        max_retries=int(defaults_raw["max_retries"]),
        timeout_seconds=float(defaults_raw["timeout_seconds"]),
        max_failure_rate=float(defaults_raw["max_failure_rate"]),
    )

    sources_raw = raw["sources"]
    if not isinstance(sources_raw, dict):
        raise ConfigError("sources", "must be a mapping of source name to source config")

    sources: dict[str, SourceConfig] = {}
    for name, source_raw in sources_raw.items():
        for key in _REQUIRED_SOURCE:
            if key not in source_raw:
                raise ConfigError(f"sources.{name}.{key}", "required key is missing")
        sources[name] = SourceConfig(
            name=name,
            enabled=bool(source_raw["enabled"]),
            host=source_raw["host"],
            strategy=source_raw["strategy"],
            min_interval_seconds=float(
                source_raw.get("min_interval_seconds", defaults.min_interval_seconds)
            ),
        )

    identity_overrides: dict[str, IdentityOverride] = {}
    overrides_raw = raw.get("identity_overrides", {}) or {}
    if not isinstance(overrides_raw, dict):
        raise ConfigError("identity_overrides", "must be a mapping of host to override")
    for host, override_raw in overrides_raw.items():
        for key in ("user_agent", "reason"):
            if key not in override_raw:
                raise ConfigError(f"identity_overrides.{host}.{key}", "required key is missing")
        identity_overrides[host] = IdentityOverride(
            user_agent=override_raw["user_agent"], reason=override_raw["reason"]
        )

    return Config(
        contact_email=contact_email,
        window=window,
        defaults=defaults,
        sources=sources,
        sha256=sha256,
        identity_overrides=identity_overrides,
    )
