import threading

import pytest

from feature_flags.models import FlagConfig
from feature_flags.store import InMemoryConfigStore


@pytest.fixture
def store() -> InMemoryConfigStore:
    return InMemoryConfigStore()


@pytest.fixture
def sample_flag() -> FlagConfig:
    return FlagConfig(name="dark_mode", env="prod", type="bool", default_value=False)


class TestSetGet:
    def test_set_then_get_returns_config(self, store, sample_flag):
        store.set(sample_flag)
        assert store.get("dark_mode", "prod") == sample_flag

    def test_get_missing_returns_none(self, store):
        assert store.get("nope", "prod") is None

    def test_get_wrong_env_returns_none(self, store, sample_flag):
        store.set(sample_flag)
        assert store.get("dark_mode", "dev") is None

    def test_same_name_different_envs_isolated(self, store):
        prod_flag = FlagConfig(name="x", env="prod", type="bool", default_value=False)
        dev_flag = FlagConfig(name="x", env="dev", type="bool", default_value=True)
        store.set(prod_flag)
        store.set(dev_flag)
        assert store.get("x", "prod") == prod_flag
        assert store.get("x", "dev") == dev_flag

    def test_set_overwrites(self, store):
        v1 = FlagConfig(name="x", env="prod", type="bool", default_value=False)
        v2 = FlagConfig(name="x", env="prod", type="bool", default_value=True)
        store.set(v1)
        store.set(v2)
        assert store.get("x", "prod") == v2


class TestSubscribe:
    def test_subscriber_called_on_set(self, store, sample_flag):
        received = []
        store.subscribe(lambda c: received.append(c))
        store.set(sample_flag)
        assert received == [sample_flag]

    def test_multiple_subscribers_all_called(self, store, sample_flag):
        a, b = [], []
        store.subscribe(lambda c: a.append(c))
        store.subscribe(lambda c: b.append(c))
        store.set(sample_flag)
        assert a == [sample_flag]
        assert b == [sample_flag]

    def test_subscriber_called_for_every_set(self, store):
        received = []
        store.subscribe(lambda c: received.append(c))
        v1 = FlagConfig(name="x", env="prod", type="bool", default_value=False)
        v2 = FlagConfig(name="x", env="prod", type="bool", default_value=True)
        store.set(v1)
        store.set(v2)
        assert received == [v1, v2]


class TestListAll:
    def test_empty_store(self, store):
        assert store.list_all() == []

    def test_returns_all_configs(self, store):
        a = FlagConfig(name="a", env="prod", type="bool", default_value=False)
        b = FlagConfig(name="b", env="dev", type="bool", default_value=True)
        store.set(a)
        store.set(b)
        assert set(store.list_all()) == {a, b}


class TestThreadSafety:
    def test_concurrent_sets_dont_corrupt(self, store):
        def writer(i: int) -> None:
            cfg = FlagConfig(name=f"f{i}", env="prod", type="bool", default_value=False)
            store.set(cfg)

        threads = [threading.Thread(target=writer, args=(i,)) for i in range(100)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        for i in range(100):
            assert store.get(f"f{i}", "prod") is not None
