"""Rate limiter utility for API calls."""

import time
import threading
from typing import Optional


class RateLimiter:
    """Token bucket rate limiter for controlling API request rates."""

    def __init__(self, max_requests: int, time_window: float):
        """
        Initialize rate limiter.

        Args:
            max_requests: Maximum number of requests allowed in the time window
            time_window: Time window in seconds
        """
        self.max_requests = max_requests
        self.time_window = time_window
        self.tokens = max_requests
        self.last_update = time.time()
        self.lock = threading.Lock()

    def _refill_tokens(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_update

        # Calculate tokens to add based on elapsed time
        tokens_to_add = (elapsed / self.time_window) * self.max_requests
        self.tokens = min(self.max_requests, self.tokens + tokens_to_add)
        self.last_update = now

    def acquire(self, timeout: Optional[float] = None) -> bool:
        """
        Acquire a token for making a request.

        Args:
            timeout: Maximum time to wait for a token in seconds. If None, waits indefinitely.

        Returns:
            True if token was acquired, False if timeout occurred
        """
        start_time = time.time()

        while True:
            with self.lock:
                self._refill_tokens()

                if self.tokens >= 1:
                    self.tokens -= 1
                    return True

                # Calculate time until next token is available
                wait_time = (1 - self.tokens) * (self.time_window / self.max_requests)

            # Check timeout
            if timeout is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout:
                    return False
                wait_time = min(wait_time, timeout - elapsed)

            time.sleep(wait_time)

    def __enter__(self):
        """Context manager entry."""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        pass
