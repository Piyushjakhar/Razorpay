import pytest

from feature_flags.models import FlagConfig
from feature_flags.service import FlagService
from feature_flags.store import InMemoryConfigStore


@pytest.fixture
def store() -> InMemoryConfigStore:
    return InMemoryConfigStore()


@pytest.fixture
def service(store) -> FlagService:
    return FlagService(store)


def test_update_flag_makes_it_retrievable(service):
    cfg = FlagConfig(name="x", env="prod", type="bool", default_value=False)
    service.update_flag(cfg)
    assert service.get_flag("x", "prod") == cfg


def test_initial_sync_from_store(store):
    cfg = FlagConfig(name="x", env="prod", type="bool", default_value=False)
    store.set(cfg)

    svc = FlagService(store)

    assert svc.get_flag("x", "prod") == cfg


def test_store_change_propagates_via_subscriber(store, service):
    cfg = FlagConfig(name="x", env="prod", type="bool", default_value=False)
    store.set(cfg)
    assert service.get_flag("x", "prod") == cfg


def test_update_flag_writes_through_to_store(store, service):
    cfg = FlagConfig(name="x", env="prod", type="bool", default_value=False)
    service.update_flag(cfg)
    assert store.get("x", "prod") == cfg


def test_get_missing_returns_none(service):
    assert service.get_flag("nope", "prod") is None
