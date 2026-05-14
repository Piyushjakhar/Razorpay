import pytest

from feature_flags.evaluator import Evaluator
from feature_flags.models import EvaluationContext, FlagConfig, TargetingRule


@pytest.fixture
def evaluator() -> Evaluator:
    return Evaluator()


@pytest.fixture
def ctx() -> EvaluationContext:
    return EvaluationContext(user_id="alice", tenant_id="acme")


class TestDefaultPath:
    def test_returns_bool_default(self, evaluator, ctx):
        cfg = FlagConfig(name="x", env="prod", type="bool", default_value=False)
        assert evaluator.evaluate(cfg, ctx) is False

    def test_returns_true_default(self, evaluator, ctx):
        cfg = FlagConfig(name="x", env="prod", type="bool", default_value=True)
        assert evaluator.evaluate(cfg, ctx) is True

    def test_returns_string_default(self, evaluator, ctx):
        cfg = FlagConfig(name="x", env="prod", type="string", default_value="blue")
        assert evaluator.evaluate(cfg, ctx) == "blue"

    def test_returns_int_default(self, evaluator, ctx):
        cfg = FlagConfig(name="x", env="prod", type="int", default_value=42)
        assert evaluator.evaluate(cfg, ctx) == 42

    def test_no_rules_returns_default(self, evaluator):
        cfg = FlagConfig(name="x", env="prod", type="string", default_value="blue")
        ctx = EvaluationContext(
            user_id="alice", tenant_id="acme", attributes={"country": "IN"}
        )
        assert evaluator.evaluate(cfg, ctx) == "blue"


class TestTargetingRules:
    def test_single_rule_matches_returns_rule_value(self, evaluator):
        rule = TargetingRule(attribute="country", value="IN", return_value=True)
        cfg = FlagConfig(
            name="x",
            env="prod",
            type="bool",
            default_value=False,
            targeting_rules=(rule,),
        )
        ctx = EvaluationContext(
            user_id="alice", tenant_id="acme", attributes={"country": "IN"}
        )
        assert evaluator.evaluate(cfg, ctx) is True

    def test_single_rule_no_match_falls_through_to_default(self, evaluator):
        rule = TargetingRule(attribute="country", value="IN", return_value=True)
        cfg = FlagConfig(
            name="x",
            env="prod",
            type="bool",
            default_value=False,
            targeting_rules=(rule,),
        )
        ctx = EvaluationContext(
            user_id="alice", tenant_id="acme", attributes={"country": "US"}
        )
        assert evaluator.evaluate(cfg, ctx) is False

    def test_missing_attribute_does_not_match(self, evaluator):
        """If the rule's attribute isn't in the context, the rule doesn't match."""
        rule = TargetingRule(attribute="country", value="IN", return_value=True)
        cfg = FlagConfig(
            name="x",
            env="prod",
            type="bool",
            default_value=False,
            targeting_rules=(rule,),
        )
        ctx = EvaluationContext(user_id="alice", tenant_id="acme", attributes={})
        assert evaluator.evaluate(cfg, ctx) is False

    def test_first_match_wins_short_circuits(self, evaluator):
        """Rules evaluated in order — first match returns, later rules ignored."""
        r1 = TargetingRule(attribute="country", value="IN", return_value="india")
        r2 = TargetingRule(attribute="country", value="IN", return_value="india_v2")
        cfg = FlagConfig(
            name="x",
            env="prod",
            type="string",
            default_value="default",
            targeting_rules=(r1, r2),
        )
        ctx = EvaluationContext(
            user_id="alice", tenant_id="acme", attributes={"country": "IN"}
        )
        assert evaluator.evaluate(cfg, ctx) == "india"

    def test_second_rule_matches_when_first_does_not(self, evaluator):
        r1 = TargetingRule(attribute="country", value="IN", return_value="india")
        r2 = TargetingRule(attribute="tier", value="gold", return_value="gold_user")
        cfg = FlagConfig(
            name="x",
            env="prod",
            type="string",
            default_value="default",
            targeting_rules=(r1, r2),
        )
        ctx = EvaluationContext(
            user_id="alice",
            tenant_id="acme",
            attributes={"country": "US", "tier": "gold"},
        )
        assert evaluator.evaluate(cfg, ctx) == "gold_user"

    def test_no_rule_matches_returns_default(self, evaluator):
        r1 = TargetingRule(attribute="country", value="IN", return_value="india")
        r2 = TargetingRule(attribute="tier", value="gold", return_value="gold_user")
        cfg = FlagConfig(
            name="x",
            env="prod",
            type="string",
            default_value="default",
            targeting_rules=(r1, r2),
        )
        ctx = EvaluationContext(
            user_id="alice",
            tenant_id="acme",
            attributes={"country": "US", "tier": "bronze"},
        )
        assert evaluator.evaluate(cfg, ctx) == "default"

    def test_rule_value_is_strict_equality(self, evaluator):
        """Rule matching is `==`, no case-insensitive or fuzzy matching."""
        rule = TargetingRule(attribute="country", value="IN", return_value=True)
        cfg = FlagConfig(
            name="x",
            env="prod",
            type="bool",
            default_value=False,
            targeting_rules=(rule,),
        )
        ctx = EvaluationContext(
            user_id="alice", tenant_id="acme", attributes={"country": "in"}
        )
        assert evaluator.evaluate(cfg, ctx) is False

    def test_rules_work_for_int_flag(self, evaluator):
        rule = TargetingRule(attribute="tier", value="gold", return_value=100)
        cfg = FlagConfig(
            name="x",
            env="prod",
            type="int",
            default_value=10,
            targeting_rules=(rule,),
        )
        ctx = EvaluationContext(
            user_id="alice", tenant_id="acme", attributes={"tier": "gold"}
        )
        assert evaluator.evaluate(cfg, ctx) == 100

    def test_rule_with_int_attribute_value(self, evaluator):
        """Rule values can be non-string types — comparison is by ==."""
        rule = TargetingRule(attribute="age", value=18, return_value=True)
        cfg = FlagConfig(
            name="x",
            env="prod",
            type="bool",
            default_value=False,
            targeting_rules=(rule,),
        )
        ctx = EvaluationContext(
            user_id="alice", tenant_id="acme", attributes={"age": 18}
        )
        assert evaluator.evaluate(cfg, ctx) is True
