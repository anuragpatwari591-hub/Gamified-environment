from conftest import ADMIN_PW, login, post, token
from seed.seed import DEMO_EMAIL, DEMO_PASSWORD


def test_register_login_logout(client):
    r = post(client, "/register", {"name": "Asha", "email": "a@example.com", "password": "Str0ng-pass!"})
    assert r.status_code == 302 and "/onboarding" in r.headers["Location"]
    assert client.get("/dashboard").status_code == 302          # not onboarded yet
    post(client, "/logout")
    assert client.get("/onboarding").status_code == 302          # logged out -> login redirect
    assert login(client, "a@example.com", "Str0ng-pass!").status_code == 302


def test_register_validation(client):
    for data in [{"name": "", "email": "x@example.com", "password": "Str0ng-pass!"},
                 {"name": "A", "email": "not-an-email", "password": "Str0ng-pass!"},
                 {"name": "A", "email": "x@example.com", "password": "short1"},
                 {"name": "A", "email": "x@example.com", "password": "12345678"}]:
        assert post(client, "/register", data).status_code == 400


def test_duplicate_email_rejected(client):
    d = {"name": "A", "email": "dup@example.com", "password": "Str0ng-pass!"}
    assert post(client, "/register", d).status_code == 302
    post(client, "/logout")
    assert post(client, "/register", dict(d, email="DUP@example.com")).status_code == 400


def test_invalid_credentials_generic_message(client):
    r = login(client, DEMO_EMAIL, "wrong-password")
    assert r.status_code == 401
    r2 = login(client, "nobody@example.com", "whatever12")
    assert r2.status_code == 401
    assert "Incorrect email or password" in r.get_data(as_text=True)


def test_passwords_are_hashed(app):
    from app.db import q1
    with app.app_context():
        h = q1("SELECT password_hash FROM users WHERE email=?", (DEMO_EMAIL,))["password_hash"]
    assert DEMO_PASSWORD not in h and h.startswith(("scrypt:", "pbkdf2:"))


def test_csrf_required(client):
    r = client.post("/login", data={"email": DEMO_EMAIL, "password": DEMO_PASSWORD})
    assert r.status_code == 400


def test_csrf_on_state_changing_learner_post(demo):
    assert demo.post("/log-session", data={"minutes": "30"}).status_code == 400


def test_login_required_redirects(client):
    for path in ["/dashboard", "/next", "/roadmap", "/skill-gap", "/bookmarks", "/progress", "/mentor", "/semester"]:
        r = client.get(path)
        assert r.status_code == 302 and "/login" in r.headers["Location"], path


def test_api_requires_auth(client):
    assert client.get("/api/next").status_code == 401
    assert client.post("/api/mentor", json={"message": "hi"}, headers={"X-CSRF-Token": token(client)}).status_code == 401


def test_open_redirect_blocked(client):
    r = post(client, "/login", {"email": DEMO_EMAIL, "password": DEMO_PASSWORD, "next": "https://evil.example/"})
    assert r.status_code == 302 and "evil.example" not in r.headers["Location"]


def test_student_cannot_access_admin(demo):
    for path in ["/admin/", "/admin/users", "/admin/e/resources", "/admin/reports"]:
        assert demo.get(path).status_code == 403, path


def test_anonymous_admin_redirects_to_login(client):
    assert client.get("/admin/").status_code == 302


def test_admin_login_ok(admin):
    assert admin.get("/admin/").status_code == 200


def test_security_headers(client):
    r = client.get("/")
    assert r.headers["X-Frame-Options"] == "DENY" and "default-src 'self'" in r.headers["Content-Security-Policy"]
    assert "script-src 'self'" in r.headers["Content-Security-Policy"]


def test_session_cookie_flags(client):
    r = login(client, DEMO_EMAIL, DEMO_PASSWORD)
    cookie = r.headers.get("Set-Cookie", "")
    assert "HttpOnly" in cookie and "SameSite=Lax" in cookie


def test_deactivated_user_cannot_use_session(app, client):
    from app.db import run
    login(client, DEMO_EMAIL, DEMO_PASSWORD)
    assert client.get("/dashboard").status_code == 200
    with app.app_context():
        run("UPDATE users SET is_active=0 WHERE email=?", (DEMO_EMAIL,))
    assert client.get("/dashboard").status_code == 302
    assert login(client, DEMO_EMAIL, DEMO_PASSWORD).status_code == 401


def test_login_rate_limit(app, client):
    codes = [login(client, "x@example.com", "bad-password-1").status_code for _ in range(10)]
    assert 429 in codes


def test_sql_injection_in_search_is_inert(client):
    r = client.get("/resources", query_string={"q": "' OR 1=1; DROP TABLE resources;--"})
    assert r.status_code == 200
    assert client.get("/resources").status_code == 200       # table still exists


def test_xss_is_escaped(student):
    post(student, "/register")  # no-op, keeps session
    r = student.get("/resources", query_string={"q": "<script>alert(1)</script>"})
    body = r.get_data(as_text=True)
    assert "<script>alert(1)</script>" not in body and "&lt;script&gt;" in body


def test_error_pages_have_no_stack_traces(client):
    r = client.get("/definitely-not-a-page")
    body = r.get_data(as_text=True)
    assert r.status_code == 404 and "Traceback" not in body and "find that page" in body

