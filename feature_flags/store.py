import threading
from typing import Callable

from feature_flags.models import FlagConfig

Subscriber = Callable[[FlagConfig], None]


class InMemoryConfigStore:
    def __init__(self) -> None:
        self._configs: dict[tuple[str, str], FlagConfig] = {}
        self._subscribers: list[Subscriber] = []
        self._lock = threading.RLock()

    def set(self, flag_config: FlagConfig) -> None:
        with self._lock:
            self._configs[(flag_config.env, flag_config.name)] = flag_config
            subs = list(self._subscribers)
        for sub in subs:
            sub(flag_config)

    def get(self, flag_name: str, env: str) -> FlagConfig | None:
        with self._lock:
            return self._configs.get((env, flag_name))

    def list_all(self) -> list[FlagConfig]:
        with self._lock:
            return list(self._configs.values())

    def subscribe(self, callback: Subscriber) -> None:
        with self._lock:
            self._subscribers.append(callback)
