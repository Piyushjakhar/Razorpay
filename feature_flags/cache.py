import threading

from feature_flags.models import FlagConfig


class LocalCache:
    def __init__(self) -> None:
        self._configs: dict[tuple[str, str], FlagConfig] = {}
        self._lock = threading.RLock()

    def set(self, flag_config: FlagConfig) -> bool:
        """Monotonic write. Returns True if accepted, False if rejected as stale."""
        key = (flag_config.env, flag_config.name)
        with self._lock:
            existing = self._configs.get(key)
            if existing is not None and flag_config.version < existing.version:
                return False
            self._configs[key] = flag_config
            return True

    def get(self, flag_name: str, env: str) -> FlagConfig | None:
        return self._configs.get((env, flag_name))
