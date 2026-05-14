import threading

from feature_flags.models import FlagConfig


class LocalCache:
    def __init__(self) -> None:
        self._configs: dict[tuple[str, str], FlagConfig] = {}
        self._lock = threading.RLock()

    def set(self, flag_config: FlagConfig) -> None:
        with self._lock:
            self._configs[(flag_config.env, flag_config.name)] = flag_config

    def get(self, flag_name: str, env: str) -> FlagConfig | None:
        return self._configs.get((env, flag_name))
