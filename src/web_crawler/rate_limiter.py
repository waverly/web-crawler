from threading import Lock
from time import time, sleep
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """Token bucket rate limiter for API calls."""

    def __init__(self, calls_per_minute: int = 60):
        self.calls_per_minute = calls_per_minute
        self.interval = 60.0 / calls_per_minute  # time between tokens
        self.last_check = time()
        self.tokens = 0.0
        self.max_tokens = 3  # allow some bursting
        self.lock = Lock()

    def wait(self):
        """Wait if needed to stay within rate limits."""
        with self.lock:
            now = time()
            # Add tokens based on time passed
            time_passed = now - self.last_check
            self.tokens = min(self.max_tokens, self.tokens + time_passed / self.interval)

            if self.tokens < 1:
                # Need to wait
                sleep_time = self.interval * (1 - self.tokens)
                sleep(sleep_time)
                self.tokens = 0
            else:
                self.tokens -= 1

            self.last_check = now
