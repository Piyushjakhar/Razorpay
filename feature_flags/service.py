import dataclasses
import logging
import threading
from typing import Any

from feature_flags.cache import LocalCache
from feature_flags.evaluator import Evaluator
from feature_flags.models import EvaluationContext, FlagConfig
from feature_flags.store import InMemoryConfigStore

log = logging.getLogger(__name__)


class FlagService:
    def __init__(self, store: InMemoryConfigStore) -> None:
        self._store = store
        self._cache = LocalCache()
        self._evaluator = Evaluator()
        self._update_lock = threading.Lock()

        for config in store.list_all():
            self._cache.set(config)

        self._store.subscribe(self._on_store_change)

    def _on_store_change(self, flag_config: FlagConfig) -> None:
        self._cache.set(flag_config)

    def update_flag(self, flag_config: FlagConfig) -> None:
        with self._update_lock:
            existing = self._cache.get(flag_config.name, flag_config.env)
            next_version = (existing.version + 1) if existing else 0
            versioned = dataclasses.replace(flag_config, version=next_version)
            self._cache.set(versioned)
            self._store.set(versioned)

    def get_flag(self, flag_name: str, env: str) -> FlagConfig | None:
        return self._cache.get(flag_name, env)

    def evaluate(
        self, flag_name: str, env: str, context: EvaluationContext
    ) -> Any:
        config = self._cache.get(flag_name, env)
        if config is None:
            log.error(
                "flag_not_found",
                extra={"flag_name": flag_name, "env": env},
            )
            return None
        return self._evaluator.evaluate(config, context)
