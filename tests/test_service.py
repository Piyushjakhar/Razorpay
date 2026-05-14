import threading

import pytest

from feature_flags.models import EvaluationContext, FlagConfig, TargetingRule
from feature_flags.service import FlagService
from feature_flags.store import InMemoryConfigStore


@pytest.fixture
def store() -> InMemoryConfigStore:
    return InMemoryConfigStore()


@pytest.fixture
def service(store) -> FlagService:
    return FlagService(store)


@pytest.fixture
def ctx() -> EvaluationContext:
    return EvaluationContext(user_id="alice", tenant_id="acme")


class TestUpdateFlag:
    def test_update_flag_makes_it_retrievable(self, service):
        cfg = FlagConfig(name="x", env="prod", type="bool", default_value=False)
        service.update_flag(cfg)
        assert service.get_flag("x", "prod") == cfg

    def test_update_flag_writes_through_to_store(self, store, service):
        cfg = FlagConfig(name="x", env="prod", type="bool", default_value=False)
        service.update_flag(cfg)
        assert store.get("x", "prod") == cfg

    def test_get_missing_returns_none(self, service):
        assert service.get_flag("nope", "prod") is None


class TestInitialSyncAndPropagation:
    def test_initial_sync_from_store(self, store):
        cfg = FlagConfig(name="x", env="prod", type="bool", default_value=False)
        store.set(cfg)

        svc = FlagService(store)

        assert svc.get_flag("x", "prod") == cfg

    def test_store_change_propagates_via_subscriber(self, store, service):
        cfg = FlagConfig(name="x", env="prod", type="bool", default_value=False)
        store.set(cfg)
        assert service.get_flag("x", "prod") == cfg


class TestVersioning:
    def test_update_flag_auto_assigns_initial_version_zero(self, service):
        cfg = FlagConfig(name="x", env="prod", type="int", default_value=10)
        service.update_flag(cfg)
        assert service.get_flag("x", "prod").version == 0

    def test_update_flag_increments_version_each_call(self, service):
        for i in range(5):
            cfg = FlagConfig(name="x", env="prod", type="int", default_value=i)
            service.update_flag(cfg)
        assert service.get_flag("x", "prod").version == 4
        assert service.get_flag("x", "prod").default_value == 4

    def test_update_flag_ignores_caller_supplied_version(self, service):
        # Caller passes version=99, service overrides to 0 (first update)
        cfg = FlagConfig(
            name="x", env="prod", type="int", default_value=10, version=99
        )
        service.update_flag(cfg)
        assert service.get_flag("x", "prod").version == 0

    def test_stale_subscriber_event_does_not_revert_cache(self, service):
        """If a stale config arrives via the store subscriber, the cache must not revert."""
        # Service cache has v=2
        v2 = FlagConfig(
            name="x", env="prod", type="int", default_value=20, version=2
        )
        service._cache.set(v2)

        # Stale v=1 arrives via subscriber
        v1 = FlagConfig(
            name="x", env="prod", type="int", default_value=10, version=1
        )
        service._on_store_change(v1)

        # Cache must still have v=2
        assert service.get_flag("x", "prod") == v2

    def test_concurrent_update_flag_no_data_loss(self, service):
        """100 concurrent update_flag calls → final state is monotonic (version == 99)."""

        def writer(i: int) -> None:
            cfg = FlagConfig(name="x", env="prod", type="int", default_value=i)
            service.update_flag(cfg)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        final = service.get_flag("x", "prod")
        assert final is not None
        assert final.version == 99


class TestEvaluate:
    def test_evaluate_bool_default(self, service, ctx):
        cfg = FlagConfig(name="x", env="prod", type="bool", default_value=False)
        service.update_flag(cfg)
        assert service.evaluate("x", "prod", ctx) is False

    def test_evaluate_string_default(self, service, ctx):
        cfg = FlagConfig(name="x", env="prod", type="string", default_value="blue")
        service.update_flag(cfg)
        assert service.evaluate("x", "prod", ctx) == "blue"

    def test_evaluate_int_default(self, service, ctx):
        cfg = FlagConfig(name="x", env="prod", type="int", default_value=42)
        service.update_flag(cfg)
        assert service.evaluate("x", "prod", ctx) == 42

    def test_evaluate_missing_flag_returns_none(self, service, ctx):
        assert service.evaluate("nope", "prod", ctx) is None

    def test_evaluate_does_not_throw_on_missing_flag(self, service, ctx):
        # Should not raise; spec requires never-throws
        result = service.evaluate("nope", "prod", ctx)
        assert result is None


class TestEvaluateWithRules:
    def test_rule_match_returns_rule_value(self, service):
        rule = TargetingRule(attribute="country", value="IN", return_value=True)
        cfg = FlagConfig(
            name="x",
            env="prod",
            type="bool",
            default_value=False,
            targeting_rules=(rule,),
        )
        service.update_flag(cfg)

        ctx = EvaluationContext(
            user_id="alice", tenant_id="acme", attributes={"country": "IN"}
        )
        assert service.evaluate("x", "prod", ctx) is True

    def test_no_rule_match_returns_default(self, service):
        rule = TargetingRule(attribute="country", value="IN", return_value=True)
        cfg = FlagConfig(
            name="x",
            env="prod",
            type="bool",
            default_value=False,
            targeting_rules=(rule,),
        )
        service.update_flag(cfg)

        ctx = EvaluationContext(
            user_id="alice", tenant_id="acme", attributes={"country": "US"}
        )
        assert service.evaluate("x", "prod", ctx) is False
