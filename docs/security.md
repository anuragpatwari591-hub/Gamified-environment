# Security

| Threat | Mitigation | Where |
|---|---|---|
| Password theft | Passwords hashed with Werkzeug (`scrypt`, salted). Plain text never stored or logged. | `routes/auth.py` |
| Credential stuffing / brute force | Rate limit: login 15/5 min per IP and 8/5 min per email; registration 10/hour per IP. Same error message for unknown email and wrong password; constant-time dummy hash check. | `security.rate_limited`, `auth.login` |
| Session theft | HTTP-only, SameSite=Lax cookies; `COOKIE_SECURE=1` for HTTPS; session cleared on login/logout; 7-day lifetime; deactivated users are logged out on the next request. | `config.py`, `security.load_user` |
| CSRF | Per-session token required on every POST/PUT/PATCH/DELETE (form field or `X-CSRF-Token` header), compared in constant time. | `security.csrf_protect` |
| SQL injection | Every user value is a bound parameter. The only dynamic SQL fragments (sort column, admin table/column names) come from fixed whitelists in code, never from requests. | `core.search_resources`, `routes/admin.py` |
| XSS | Jinja autoescape on; no `|safe` on user data; strict CSP `script-src 'self'` (no inline scripts, no inline handlers); `X-Content-Type-Options: nosniff`. | templates, `security.add_headers` |
| Clickjacking | `X-Frame-Options: DENY` and `frame-ancestors 'none'`. | `add_headers` |
| Open redirect | `next` parameters accepted only if they are same-site relative paths. | `security.safe_next` |
| Unauthorised access | `@login_required` on learner routes; `/admin/*` guarded by a blueprint-level `before_request` that returns 403 for non-admins; admin cannot deactivate themselves. | `security.py`, `routes/admin.py` |
| Malicious URLs | Admin-entered URLs must be http(s); user-entered repository links must be http(s). Outbound links use `rel="noopener nofollow sponsored"`. | `admin.parse`, `learner.project_status` |
| Oversized requests | `MAX_CONTENT_LENGTH` 256 KB; text fields length-capped. | `config.py`, routes |
| Information leakage | Custom 400/403/404/413/429/500 pages; stack traces go to the server log only. | `app/__init__.py` |
| Secrets in git | `.env`, `instance/`, `*.db` ignored; `.env.example` has placeholders only; admin password is generated at seed time and printed once. | `.gitignore`, `seed.py` |
| Auditability | Admin writes are recorded in `audit_logs`. | `routes/admin.audit` |

## Known limitations (be honest in a viva)

* The rate limiter is in-memory and per process: fine for one instance, not for several workers. Use Redis/Flask-Limiter in production.
* No email verification or password reset yet (no email service). Account recovery is manual via the operator.
* No two-factor authentication for admins.
* The demo account is shared and its password is documented, by design.
* `style-src 'unsafe-inline'` is allowed because a few elements use inline `style=` for dynamic widths.
* The optional LLM adapter sends mentor questions to a third party if enabled; the privacy policy says so.
* Run behind HTTPS in production and set `COOKIE_SECURE=1`.

## Dependency hygiene

Only Flask (and gunicorn for deployment) are runtime dependencies. Run `pip list --outdated` / `pip-audit` before release.
