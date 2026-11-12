
from contextlib import contextmanager
import threading
import time
from collections import defaultdict


class CampusMetrics:
    def __init__(self):
        self.lock = threading.Lock()
        self.started_at = time.time()

        self.total_requests = 0
        self.cache_hits = 0
        self.cache_misses = 0
        self.gemini_calls = 0
        self.errors = 0

        self.stage_times = defaultdict(lambda: [0, 0.0])
        self.response_times = []
        self.status_codes = defaultdict(int)

    @contextmanager
    def stage(self, name):
        start = time.perf_counter()
        try:
            yield
        finally:
            with self.lock:
                stats = self.stage_times[name]
                stats[0] += 1
                stats[1] += time.perf_counter() - start

    def record_request(self, duration, status_code):
        with self.lock:
            self.total_requests += 1
            self.response_times.append(duration)
            self.status_codes[str(status_code)] += 1

            if len(self.response_times) > 1000:
                self.response_times.pop(0)

            if status_code >= 500:
                self.errors += 1

    def record_cache_hit(self):
        with self.lock:
            self.cache_hits += 1

    def record_cache_miss(self):
        with self.lock:
            self.cache_misses += 1

    def record_gemini_call(self):
        with self.lock:
            self.gemini_calls += 1

    def get_metrics(self):
        with self.lock:
            average_time = (
                sum(self.response_times)
                / len(self.response_times)
                if self.response_times
                else 0
            )

            total_cache_checks = (
                self.cache_hits + self.cache_misses
            )

            hit_rate = (
                self.cache_hits / total_cache_checks * 100
                if total_cache_checks
                else 0
            )

            return {
                "stages": {name: {"calls": stats[0], "total_seconds": round(stats[1], 6),
                                  "mean_seconds": round(stats[1] / stats[0], 6)}
                           for name, stats in self.stage_times.items()},
                "uptime_seconds": round(
                    time.time() - self.started_at, 2
                ),
                "total_requests": self.total_requests,
                "cache_hits": self.cache_hits,
                "cache_misses": self.cache_misses,
                "cache_hit_rate_percent": round(hit_rate, 2),
                "gemini_calls": self.gemini_calls,
                "server_errors": self.errors,
                "average_response_time_seconds": round(
                    average_time, 3
                ),
                "status_codes": dict(self.status_codes)
            }


metrics = CampusMetrics()

