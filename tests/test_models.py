import pytest

from feature_flags.models import EvaluationContext, FlagConfig, TargetingRule


class TestFlagConfig:
    def test_minimal_construction(self):
        config = FlagConfig(
            name="dark_mode", env="prod", type="bool", default_value=False
        )
        assert config.name == "dark_mode"
        assert config.env == "prod"
        assert config.type == "bool"
        assert config.default_value is False
        assert config.targeting_rules == ()
        assert config.rollout_percentage == 0
        assert config.rollout_value is None
        assert config.bucketing_group is None
        assert config.version == 0

    def test_full_construction(self):
        rule = TargetingRule(attribute="country", value="IN", return_value=True)
        config = FlagConfig(
            name="dark_mode",
            env="prod",
            type="bool",
            default_value=False,
            targeting_rules=(rule,),
            rollout_percentage=30,
            rollout_value=True,
            bucketing_group="early_access",
        )
        assert config.targeting_rules == (rule,)
        assert config.rollout_percentage == 30
        assert config.rollout_value is True
        assert config.bucketing_group == "early_access"

    def test_is_frozen(self):
        config = FlagConfig(name="x", env="prod", type="bool", default_value=False)
        with pytest.raises(Exception):
            config.name = "y"  # type: ignore[misc]


class TestTargetingRule:
    def test_construction(self):
        rule = TargetingRule(attribute="country", value="IN", return_value=True)
        assert rule.attribute == "country"
        assert rule.value == "IN"
        assert rule.return_value is True


class TestEvaluationContext:
    def test_minimal(self):
        ctx = EvaluationContext(user_id="alice", tenant_id="acme")
        assert ctx.user_id == "alice"
        assert ctx.tenant_id == "acme"
        assert ctx.attributes == {}

    def test_with_attributes(self):
        ctx = EvaluationContext(
            user_id="alice", tenant_id="acme", attributes={"country": "IN"}
        )
        assert ctx.attributes == {"country": "IN"}
