import re
import sqlite3

from flask import Blueprint, abort, flash, g, redirect, render_template, request, session, url_for
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import q1, run
from ..security import rate_limited, safe_next

bp = Blueprint("auth", __name__)
EMAIL_RE = re.compile(r"^[^@\s]{1,64}@[^@\s]{1,255}\.[^@\s]{2,}$")
DUMMY_HASH = generate_password_hash("not-a-real-password")   # equalises timing for unknown emails


def _start_session(user):
    lang = session.get("lang")
    session.clear()
    session.permanent = True
    session["uid"] = user["id"]
    if lang:
        session["lang"] = lang
    run("UPDATE users SET last_login_at=datetime('now') WHERE id=?", (user["id"],))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if g.user:
        return redirect(url_for("learner.dashboard"))
    if request.method == "POST":
        if rate_limited(f"reg:{request.remote_addr}", 10, 3600):
            abort(429)
        name = request.form.get("name", "").strip()[:80]
        email = request.form.get("email", "").strip().lower()[:254]
        pw = request.form.get("password", "")
        errors = []
        if not name:
            errors.append("Please tell us your name.")
        if not EMAIL_RE.match(email):
            errors.append("Enter a valid email address.")
        if len(pw) < 8 or pw.isdigit() or pw.lower() == pw and pw.isalpha():
            errors.append("Use a password of at least 8 characters that mixes letters with numbers or symbols.")
        if not errors:
            try:
                cur = run("INSERT INTO users(email, name, password_hash) VALUES (?,?,?)",
                          (email, name, generate_password_hash(pw)))
                run("INSERT INTO profiles(user_id) VALUES (?)", (cur.lastrowid,))
                _start_session({"id": cur.lastrowid})
                return redirect(url_for("learner.onboarding"))
            except sqlite3.IntegrityError:
                errors.append("An account with this email already exists. Try logging in.")
        for e in errors:
            flash(e, "error")
        return render_template("auth/register.html", form=request.form), 400
    return render_template("auth/register.html", form={})


@bp.route("/login", methods=["GET", "POST"])
def login():
    if g.user:
        return redirect(url_for("learner.dashboard"))
    nxt = safe_next(request.values.get("next"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()[:254]
        if rate_limited(f"login:{request.remote_addr}", 15, 300) or rate_limited(f"loginu:{email}", 8, 300):
            abort(429)
        u = q1("SELECT * FROM users WHERE email=?", (email,))
        ok = check_password_hash(u["password_hash"] if u else DUMMY_HASH, request.form.get("password", ""))
        if u and ok and u["is_active"]:
            _start_session(u)
            if u["role"] == "admin":
                return redirect(nxt or url_for("admin.dashboard"))
            return redirect(nxt or url_for("learner.dashboard"))
        flash("Incorrect email or password, or the account is deactivated.", "error")   # same message for all failures
        return render_template("auth/login.html", next=nxt, email=email), 401
    return render_template("auth/login.html", next=nxt, email="")


@bp.route("/demo-login", methods=["POST"])
def demo_login():
    u = q1("SELECT * FROM users WHERE is_demo=1 AND is_active=1 LIMIT 1")
    if not u:
        flash("Demo data has not been seeded yet. Run: python -m seed.seed", "error")
        return redirect(url_for("auth.login"))
    _start_session(u)
    return redirect(url_for("learner.dashboard"))


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("main.home"))


@bp.route("/lang/<code>", methods=["POST"])
def set_lang(code):
    if code in ("en", "hi", "bn"):
        session["lang"] = code
        if g.user:
            run("UPDATE users SET lang=? WHERE id=?", (code, g.user["id"]))
    return redirect(safe_next(request.form.get("next")) or url_for("main.home"))
