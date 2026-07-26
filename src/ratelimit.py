import logging
import time
from collections.abc import Callable
from functools import wraps

from flask import jsonify, request, session

logger = logging.getLogger(__name__)

# In-memory rate limit store
_limits: dict[str, list[float]] = {}

def rate_limit(key_func: Callable[[], str], max_requests: int = 30, window: int = 60):
    """Decorator for rate limiting endpoints."""
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            key = key_func()
            now = time.time()
            window_start = now - window

            if key not in _limits:
                _limits[key] = []

            # Clean old entries
            _limits[key] = [t for t in _limits[key] if t > window_start]

            if len(_limits[key]) >= max_requests:
                logger.warning(f"Rate limit exceeded for {key}")
                return jsonify({
                    "status": False,
                    "error": f"Rate limit exceeded. Try again in {window} seconds.",
                    "retry_after": window
                }), 429

            _limits[key].append(now)
            return f(*args, **kwargs)
        return wrapper
    return decorator


def user_rate_limit(max_requests: int = 60, window: int = 60):
    """Rate limit by user ID or IP."""
    def key_func() -> str:
        user_id = session.get("user_id", "anonymous")
        ip = request.remote_addr or "unknown"
        return f"user:{user_id}:{ip}"
    return rate_limit(key_func, max_requests, window)


def ip_rate_limit(max_requests: int = 30, window: int = 60):
    """Rate limit by IP address only."""
    def key_func() -> str:
        return f"ip:{request.remote_addr or 'unknown'}"
    return rate_limit(key_func, max_requests, window)


# Track login attempts by IP
_login_attempts: dict[str, list[float]] = {}

def check_login_rate_limit(max_attempts: int = 5, window: int = 300) -> tuple[bool, int]:
    """
    Returns (is_allowed, retry_after_seconds).
    5 attempts per 5 minutes per IP.
    """
    ip = request.remote_addr or "unknown"
    now = time.time()

    if ip not in _login_attempts:
        _login_attempts[ip] = []

    _login_attempts[ip] = [t for t in _login_attempts[ip] if now - t < window]

    if len(_login_attempts[ip]) >= max_attempts:
        retry_after = int(window - (now - _login_attempts[ip][0]))
        return False, retry_after

    return True, 0


def record_login_attempt():
    ip = request.remote_addr or "unknown"
    if ip not in _login_attempts:
        _login_attempts[ip] = []
    _login_attempts[ip].append(time.time())
