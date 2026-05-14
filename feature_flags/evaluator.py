from typing import Any

from feature_flags.models import EvaluationContext, FlagConfig


class Evaluator:
    """Pure evaluation logic. Given a config + context, returns the flag value.

    Precedence: targeting rules (first match wins) → percentage rollout → default.
    M4 adds the rollout step; M5 adds the fail-safe wrapper.
    """

    def evaluate(self, config: FlagConfig, context: EvaluationContext) -> Any:
        for rule in config.targeting_rules:
            if context.attributes.get(rule.attribute) == rule.value:
                return rule.return_value

        return config.default_value
