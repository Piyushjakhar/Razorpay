from typing import Any

from feature_flags.models import EvaluationContext, FlagConfig


class Evaluator:
    """Pure evaluation logic. Given a config + context, returns the flag value.

    Currently implements only the default-value path. M3 adds targeting rules;
    M4 adds percentage rollout; M5 adds the fail-safe wrapper.
    """

    def evaluate(self, config: FlagConfig, context: EvaluationContext) -> Any:
        return config.default_value
