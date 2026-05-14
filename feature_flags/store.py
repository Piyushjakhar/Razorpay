import threading
from typing import Callable

from feature_flags.models import FlagConfig

Subscriber = Callable[[FlagConfig], None]


class InMemoryConfigStore:
    def __init__(self) -> None:
        self._configs: dict[tuple[str, str], FlagConfig] = {}
        self._subscribers: list[Subscriber] = []
        self._lock = threading.RLock()

    def set(self, flag_config: FlagConfig) -> bool:
        """Monotonic write. Returns True if accepted, False if rejected as stale.
        Subscribers fire only on accepted writes."""
        key = (flag_config.env, flag_config.name)
        with self._lock:
            existing = self._configs.get(key)
            if existing is not None and flag_config.version < existing.version:
                return False
            self._configs[key] = flag_config
            subs = list(self._subscribers)
        for sub in subs:
            sub(flag_config)
        return True

    def get(self, flag_name: str, env: str) -> FlagConfig | None:
        with self._lock:
            return self._configs.get((env, flag_name))

    def list_all(self) -> list[FlagConfig]:
        with self._lock:
            return list(self._configs.values())

    def subscribe(self, callback: Subscriber) -> None:
        with self._lock:
            self._subscribers.append(callback)
