from typing import Dict, Any, Optional
import time

class InMemorySessionStore:
    def __init__(self, ttl_seconds: int = 3600):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._ttl = ttl_seconds

    def get(self, user_id: str) -> Dict[str, Any]:
        s = self._store.get(user_id, {})
        # simple TTL check
        if s and (time.time() - s.get("_ts", 0) > self._ttl):
            self._store.pop(user_id, None)
            s = {}
        s["_ts"] = time.time()
        self._store[user_id] = s
        return s

    def set(self, user_id: str, data: Dict[str, Any]):
        data["_ts"] = time.time()
        self._store[user_id] = data
