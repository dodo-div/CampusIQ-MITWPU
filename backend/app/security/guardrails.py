
import re
import time
import threading
from collections import defaultdict, deque


MAX_MESSAGE_LENGTH = 2000
RATE_LIMIT = 12
RATE_WINDOW_SECONDS = 60


class SecurityError(ValueError):
    def __init__(self, message, status_code=400):
        super().__init__(message)
        self.status_code = status_code


# High-confidence instruction-override patterns.
# These are only one layer of protection.
INJECTION_PATTERNS = [
    re.compile(
        r"\b(ignore|disregard|override)\s+"
        r"(all\s+)?(previous|prior|system|developer)\s+"
        r"(instructions|rules|prompts)\b",
        re.IGNORECASE
    ),
    re.compile(
        r"\b(reveal|print|show|expose)\s+"
        r"(your\s+)?(hidden\s+)?"
        r"(system prompt|developer instructions|api key)\b",
        re.IGNORECASE
    ),
    re.compile(
        r"\b(enable|activate)\s+"
        r"(developer mode|jailbreak mode)\b",
        re.IGNORECASE
    ),
]


def validate_message(message):
    """
    Validate and screen a user message.

    Returns cleaned message or raises SecurityError.
    """

    if not isinstance(message, str):
        raise SecurityError("Message must be text.")

    message = message.strip()

    if not message:
        raise SecurityError("Message cannot be empty.")

    if len(message) > MAX_MESSAGE_LENGTH:
        raise SecurityError(
            "Message is too long. Maximum 2000 characters.",
            status_code=413
        )

    # Reject NUL and disallowed ASCII control characters.
    if any(
        ord(ch) < 32 and ch not in "\n\r\t"
        for ch in message
    ):
        raise SecurityError(
            "Message contains invalid control characters."
        )

    for pattern in INJECTION_PATTERNS:
        if pattern.search(message):
            raise SecurityError(
                "This request attempts to override "
                "CampusIQ's operating instructions."
            )

    return message


class SlidingWindowRateLimiter:
    """
    Simple thread-safe, in-memory rate limiter.

    Development use only: counters are per process.
    """

    def __init__(self, limit=RATE_LIMIT,
                 window=RATE_WINDOW_SECONDS):
        self.limit = limit
        self.window = window
        self.requests = defaultdict(deque)
        self.lock = threading.Lock()

    def check(self, client_id, now=None):
        if now is None:
            now = time.monotonic()

        with self.lock:
            # Discard expired entries.
            timestamps = self.requests[client_id]

            while (
                timestamps
                and now - timestamps[0] >= self.window
            ):
                timestamps.popleft()

            if len(timestamps) >= self.limit:
                retry_after = max(
                    1,
                    int(
                        self.window
                        - (now - timestamps[0])
                    ) + 1
                )
                return False, retry_after

            timestamps.append(now)

            # Periodic cleanup of inactive client records.
            if len(self.requests) > 1000:
                expired = [
                    key
                    for key, entries in self.requests.items()
                    if not entries
                    or now - entries[-1] >= self.window
                ]

                for key in expired:
                    del self.requests[key]

            return True, 0


rate_limiter = SlidingWindowRateLimiter()
