import pytest

from feature_flags.cache import LocalCache
from feature_flags.models import FlagConfig


@pytest.fixture
def cache() -> LocalCache:
    return LocalCache()


def test_set_then_get(cache):
    cfg = FlagConfig(name="x", env="prod", type="bool", default_value=False)
    cache.set(cfg)
    assert cache.get("x", "prod") == cfg


def test_get_missing_returns_none(cache):
    assert cache.get("nope", "prod") is None


def test_env_isolation(cache):
    p = FlagConfig(name="x", env="prod", type="bool", default_value=False)
    d = FlagConfig(name="x", env="dev", type="bool", default_value=True)
    cache.set(p)
    cache.set(d)
    assert cache.get("x", "prod") == p
    assert cache.get("x", "dev") == d


def test_set_overwrites(cache):
    v1 = FlagConfig(name="x", env="prod", type="bool", default_value=False)
    v2 = FlagConfig(name="x", env="prod", type="bool", default_value=True)
    cache.set(v1)
    cache.set(v2)
    assert cache.get("x", "prod") == v2


class TestMonotonicity:
    def test_newer_version_accepted(self, cache):
        v0 = FlagConfig(name="x", env="prod", type="int", default_value=10, version=0)
        v1 = FlagConfig(name="x", env="prod", type="int", default_value=20, version=1)
        assert cache.set(v0) is True
        assert cache.set(v1) is True
        assert cache.get("x", "prod") == v1

    def test_stale_version_rejected(self, cache):
        v0 = FlagConfig(name="x", env="prod", type="int", default_value=10, version=0)
        v1 = FlagConfig(name="x", env="prod", type="int", default_value=20, version=1)
        assert cache.set(v1) is True
        assert cache.set(v0) is False  # stale
        assert cache.get("x", "prod") == v1

    def test_same_version_overwrites(self, cache):
        v0a = FlagConfig(
            name="x", env="prod", type="int", default_value=10, version=0
        )
        v0b = FlagConfig(
            name="x", env="prod", type="int", default_value=20, version=0
        )
        assert cache.set(v0a) is True
        assert cache.set(v0b) is True
        assert cache.get("x", "prod") == v0b

    def test_monotonicity_is_per_flag(self, cache):
        a_v5 = FlagConfig(name="a", env="prod", type="int", default_value=1, version=5)
        b_v0 = FlagConfig(name="b", env="prod", type="int", default_value=2, version=0)
        cache.set(a_v5)
        # b is a different flag — its v=0 is not stale
        assert cache.set(b_v0) is True
        assert cache.get("b", "prod") == b_v0
