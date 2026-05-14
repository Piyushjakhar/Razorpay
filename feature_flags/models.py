from dataclasses import dataclass, field
from typing import Any, Literal

FlagType = Literal["bool", "string", "int"]


@dataclass(frozen=True)
class TargetingRule:
    attribute: str
    value: Any
    return_value: Any


@dataclass(frozen=True)
class FlagConfig:
    name: str
    env: str
    type: FlagType
    default_value: Any
    targeting_rules: tuple[TargetingRule, ...] = ()
    rollout_percentage: int = 0
    rollout_value: Any = None
    bucketing_group: str | None = None
    version: int = 0


@dataclass(frozen=True)
class EvaluationContext:
    user_id: str
    tenant_id: str
    attributes: dict[str, Any] = field(default_factory=dict)
