"""CSRF protection, in-memory rate limiting, security headers, and auth decorators."""
import hmac
import secrets
import time
from functools import wraps
from urllib.parse import urlparse

from flask import abort, current_app, g, redirect, request, session, url_for

from .db import q1

_hits = {}   # (key) -> [timestamps]; process-local, fine for a single-instance deployment


def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def csrf_protect():
    """Called in before_request: every state-changing request must carry the session's token."""
    if request.method in ("POST", "PUT", "PATCH", "DELETE"):
        sent = request.form.get("_csrf") or request.headers.get("X-CSRF-Token") or ""
        if not hmac.compare_digest(sent, session.get("_csrf", "")) or not sent:
            abort(400, "Invalid or missing CSRF token. Please reload the page and try again.")


def rate_limited(key, limit, window):
    if not current_app.config.get("RATE_LIMIT_ENABLED", True):
        return False
    now = time.time()
    arr = [t for t in _hits.get(key, []) if now - t < window]
    arr.append(now)
    _hits[key] = arr
    return len(arr) > limit


def reset_rate_limits():
    _hits.clear()


def add_headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    resp.headers["Content-Security-Policy"] = (
        "default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; "
        "font-src 'self'; frame-ancestors 'none'; form-action 'self'; base-uri 'self'")
    return resp


def load_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        u = q1("SELECT id, email, name, role, is_active, is_demo, lang FROM users WHERE id=?", (uid,))
        if u and u["is_active"]:
            g.user = u
        else:
            session.clear()


def login_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.path))
        return f(*a, **kw)
    return wrapper


def admin_required(f):
    @wraps(f)
    def wrapper(*a, **kw):
        if g.user is None:
            return redirect(url_for("auth.login", next=request.path))
        if g.user["role"] != "admin":
            abort(403)
        return f(*a, **kw)
    return wrapper


def safe_next(target):
    """Only allow same-site relative redirects (prevents open redirect)."""
    if not target:
        return None
    p = urlparse(target)
    if p.scheme or p.netloc or not target.startswith("/") or target.startswith("//") or "\\" in target:
        return None
    return target
