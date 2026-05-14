from feature_flags.cache import LocalCache
from feature_flags.models import FlagConfig
from feature_flags.store import InMemoryConfigStore


class FlagService:
    def __init__(self, store: InMemoryConfigStore) -> None:
        self._store = store
        self._cache = LocalCache()

        for config in store.list_all():
            self._cache.set(config)

        self._store.subscribe(self._on_store_change)

    def _on_store_change(self, flag_config: FlagConfig) -> None:
        self._cache.set(flag_config)

    def update_flag(self, flag_config: FlagConfig) -> None:
        self._cache.set(flag_config)
        self._store.set(flag_config)

    def get_flag(self, flag_name: str, env: str) -> FlagConfig | None:
        return self._cache.get(flag_name, env)
