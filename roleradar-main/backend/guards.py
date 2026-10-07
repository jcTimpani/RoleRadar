"""Shared request guards: admin-token check and small in-memory rate limiter."""
import os
import time
import hmac
import collections
from typing import Optional

from fastapi import HTTPException, Header, Request


def require_admin(x_admin_token: Optional[str] = Header(None)):
    """Guard for destructive or quota-burning endpoints (wipe DB, crawlers, raw inserts).
    Disabled entirely (403) unless ADMIN_TOKEN is configured in the environment."""
    expected = os.environ.get("ADMIN_TOKEN")
    if not expected or not x_admin_token or not hmac.compare_digest(x_admin_token, expected):
        raise HTTPException(status_code=403, detail="Admin access required")


_rate_hits = collections.defaultdict(collections.deque)


def rate_limit(name: str, per_ip: int, overall: int, window: int = 60):
    """Small in-memory limiter for endpoints that spend API quota or are abuse targets.
    `per_ip` limits one visitor, `overall` caps the whole service."""
    def check(request: Request):
        forwarded = request.headers.get("x-forwarded-for", "").split(",")[0].strip()
        ip = forwarded or (request.client.host if request.client else "unknown")
        now = time.time()
        for key, cap in (((name, ip), per_ip), ((name, "*"), overall)):
            hits = _rate_hits[key]
            while hits and now - hits[0] > window:
                hits.popleft()
            if len(hits) >= cap:
                raise HTTPException(status_code=429, detail="Too many requests right now. Please wait a minute and try again.")
        _rate_hits[(name, ip)].append(now)
        _rate_hits[(name, "*")].append(now)
    return check
