import pytest

from feature_flags.evaluator import Evaluator
from feature_flags.models import EvaluationContext, FlagConfig


@pytest.fixture
def evaluator() -> Evaluator:
    return Evaluator()


@pytest.fixture
def ctx() -> EvaluationContext:
    return EvaluationContext(user_id="alice", tenant_id="acme")


def test_returns_bool_default(evaluator, ctx):
    cfg = FlagConfig(name="x", env="prod", type="bool", default_value=False)
    assert evaluator.evaluate(cfg, ctx) is False


def test_returns_true_default(evaluator, ctx):
    cfg = FlagConfig(name="x", env="prod", type="bool", default_value=True)
    assert evaluator.evaluate(cfg, ctx) is True


def test_returns_string_default(evaluator, ctx):
    cfg = FlagConfig(name="x", env="prod", type="string", default_value="blue")
    assert evaluator.evaluate(cfg, ctx) == "blue"


def test_returns_int_default(evaluator, ctx):
    cfg = FlagConfig(name="x", env="prod", type="int", default_value=42)
    assert evaluator.evaluate(cfg, ctx) == 42


def test_ignores_context_attributes_in_default_path(evaluator):
    """M2 doesn't use rules or rollout — context attributes are ignored."""
    cfg = FlagConfig(name="x", env="prod", type="string", default_value="blue")
    ctx = EvaluationContext(
        user_id="alice", tenant_id="acme", attributes={"country": "IN"}
    )
    assert evaluator.evaluate(cfg, ctx) == "blue"
