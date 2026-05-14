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
