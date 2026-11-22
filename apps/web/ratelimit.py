"""Small cache-backed rate limiter for uploads and analysis endpoints (login lockout is handled by django-axes)."""
from __future__ import annotations

from functools import wraps

from django.core.cache import cache
from django.http import HttpResponse


def _identity(request) -> str:
    return f"u{request.user.pk}" if request.user.is_authenticated else f"ip{request.META.get('REMOTE_ADDR', '?')}"


def hit(request, scope: str, limit: int, window_seconds: int) -> bool:
    """Count this request; return True if it is over the limit."""
    key = f"rl:{scope}:{_identity(request)}"
    cache.add(key, 0, window_seconds)
    try:
        count = cache.incr(key)
    except ValueError:      # key expired between add and incr
        cache.set(key, 1, window_seconds)
        count = 1
    return count > limit


def rate_limit(scope: str, limit: int, window_seconds: int):
    def deco(view):
        @wraps(view)
        def wrapper(request, *a, **kw):
            if request.method == "POST" and hit(request, scope, limit, window_seconds):
                return HttpResponse("Too many requests. Please wait a few minutes and try again.", status=429, content_type="text/plain")
            return view(request, *a, **kw)
        return wrapper
    return deco
