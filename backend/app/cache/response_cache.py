
import copy
import hashlib
import json
import threading
import time
from collections import OrderedDict


class ResponseCache:
    """
    Thread-safe in-memory cache for CampusIQ.

    - Exact normalized question matching
    - TTL expiration
    - Maximum number of cached responses
    - Cache namespace for knowledge-base versions
    """

    def __init__(self, max_size=500, ttl=3600):
        self.max_size = max_size
        self.ttl = ttl
        self.storage = OrderedDict()
        self.lock = threading.Lock()

    def make_key(self, question, namespace="v1"):
        normalized = " ".join(
            question.casefold().split()
        )

        payload = json.dumps(
            [namespace, normalized],
            ensure_ascii=False
        )

        return hashlib.sha256(
            payload.encode("utf-8")
        ).hexdigest()

    def get(self, question, namespace="v1"):
        key = self.make_key(question, namespace)

        with self.lock:
            entry = self.storage.get(key)

            if entry is None:
                return None

            expires_at, response = entry

            if time.monotonic() >= expires_at:
                del self.storage[key]
                return None

            self.storage.move_to_end(key)

            return copy.deepcopy(response)

    def set(self, question, response, namespace="v1"):
        key = self.make_key(question, namespace)

        with self.lock:
            self.storage[key] = (
                time.monotonic() + self.ttl,
                copy.deepcopy(response)
            )

            self.storage.move_to_end(key)

            while len(self.storage) > self.max_size:
                self.storage.popitem(last=False)

    def clear(self):
        with self.lock:
            self.storage.clear()

    def size(self):
        with self.lock:
            return len(self.storage)


response_cache = ResponseCache()
