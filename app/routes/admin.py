"""Admin panel: generic CRUD driven by ENTITIES config, plus users, verification, reports, affiliates, analytics."""
import sqlite3
from datetime import date

from flask import Blueprint, abort, flash, g, redirect, render_template, request, url_for

from ..db import get_db, q, q1, run, scalar
from ..security import admin_required

bp = Blueprint("admin", __name__, url_prefix="/admin")

SELECT_OPTS = {
    "resource_type": ["course", "video", "documentation", "book", "article", "practice", "project", "github", "certification"],
    "format": ["video", "reading", "interactive", "practice", "project"],
    "source_kind": ["official", "university", "government", "nonprofit", "platform", "community"],
    "pricing": ["free", "freemium", "paid"],
    "status": ["unverified", "active", "broken", "outdated", "hidden"],
    "difficulty": ["1", "2", "3"],
}


def F(name, label, kind="text", required=False, opts=None, maxlen=500):
    return {"name": name, "label": label, "kind": kind, "required": required, "opts": opts or SELECT_OPTS.get(name), "maxlen": maxlen}


ENTITIES = {
    "resources": {
        "table": "resources", "title": "Resources", "list": ["title", "provider", "pricing", "status", "last_verified_at"],
        "fields": [F("title", "Title", required=True, maxlen=200), F("provider", "Provider", required=True, maxlen=100),
                   F("url", "URL", "url", True, maxlen=500), F("source_url", "Source URL (attribution)", "url"),
                   F("category", "Category", maxlen=60), F("topic", "Topic", maxlen=80), F("resource_type", "Type", "select"),
                   F("format", "Learning format", "select"), F("source_kind", "Source kind", "select"),
                   F("difficulty", "Difficulty", "select"), F("duration_min", "Duration (minutes)", "int"),
                   F("language", "Language", maxlen=30), F("pricing", "Pricing", "select"), F("price_inr", "Price (INR)", "int"),
                   F("price_note", "Price note", maxlen=200), F("rating", "External rating (0-5)", "float"),
                   F("rating_count", "Number of ratings", "int"), F("rating_source", "Rating source", maxlen=100),
                   F("description", "Description", "textarea"), F("prerequisites", "Prerequisites", "textarea"),
                   F("strengths", "Strengths", "textarea"), F("limitations", "Limitations", "textarea"),
                   F("suitable_for", "Suitable for", "textarea"), F("tags", "Tags (comma separated)", maxlen=200),
                   F("affiliate_url", "Affiliate URL", "url"), F("affiliate_ref", "Affiliate referral ID", maxlen=80),
                   F("commission_pct", "Commission % (if known)", "float"), F("status", "Status", "select"),
                   F("verification_notes", "Verification notes", "textarea")],
        "m2m": ("resource_skills", "resource_id"),
    },
    "skills": {"table": "skills", "title": "Skills", "list": ["name", "slug", "category"],
               "fields": [F("name", "Name", required=True, maxlen=80), F("slug", "Slug", required=True, maxlen=60),
                          F("category", "Category", maxlen=40), F("description", "Description", "textarea")]},
    "careers": {"table": "careers", "title": "Careers", "list": ["title", "slug"],
                "fields": [F("title", "Title", required=True, maxlen=100), F("slug", "Slug", required=True, maxlen=60),
                           F("description", "Description", "textarea"), F("interest_tags", "Discovery tags (comma separated)", maxlen=100),
                           F("degree_backgrounds", "Degree backgrounds", "textarea"), F("certifications", "Certifications", "textarea"),
                           F("portfolio_requirements", "Portfolio requirements", "textarea"), F("interview_prep", "Interview preparation", "textarea")]},
    "streams": {"table": "streams", "title": "Streams", "list": ["name", "group_name", "slug"],
                "fields": [F("name", "Name", required=True, maxlen=80), F("slug", "Slug", required=True, maxlen=60),
                           F("group_name", "Group", maxlen=40), F("description", "Description", "textarea")]},
    "roadmaps": {"table": "roadmaps", "title": "Roadmaps", "list": ["title", "career_id"],
                 "fields": [F("career_id", "Career", "ref:careers:title", True), F("title", "Title", required=True, maxlen=120),
                            F("description", "Description", "textarea")]},
    "stages": {"table": "roadmap_stages", "title": "Roadmap stages", "list": ["roadmap_id", "position", "title", "est_hours"],
               "fields": [F("roadmap_id", "Roadmap", "ref:roadmaps:title", True), F("position", "Position", "int", True),
                          F("title", "Title", required=True, maxlen=120), F("description", "Description", "textarea"),
                          F("concepts", "Concepts (comma separated)", "textarea"), F("skill_id", "Skill", "ref:skills:name"),
                          F("target_level", "Target skill level (1-100)", "int", True), F("est_hours", "Estimated hours", "int", True),
                          F("milestone", "Milestone", "textarea")]},
    "projects": {"table": "projects", "title": "Projects", "list": ["title", "difficulty", "est_hours"],
                 "fields": [F("title", "Title", required=True, maxlen=120), F("slug", "Slug", required=True, maxlen=60),
                            F("difficulty", "Difficulty", "select"), F("est_hours", "Estimated hours", "int", True),
                            F("description", "Description", "textarea"), F("outcomes", "Learning outcomes", "textarea"),
                            F("technologies", "Technologies", maxlen=200), F("checklist", "GitHub checklist (one per line)", "textarea"),
                            F("portfolio_blurb", "Portfolio description", "textarea")],
                 "m2m": ("project_skills", "project_id")},
    "sponsored": {"table": "sponsored_content", "title": "Sponsored content", "list": ["title", "sponsor", "active", "is_demo"],
                  "fields": [F("title", "Title", required=True, maxlen=120), F("sponsor", "Sponsor name", required=True, maxlen=100),
                             F("resource_id", "Linked resource", "ref:resources:title"), F("url", "URL", "url"),
                             F("blurb", "Blurb", "textarea"), F("is_demo", "This is demo data", "bool"), F("active", "Active (shown to users)", "bool")]},
    "quiz": {"table": "quiz_questions", "title": "Quiz questions", "list": ["skill_id", "question"],
             "fields": [F("skill_id", "Skill", "ref:skills:name", True), F("question", "Question", "textarea", True),
                        F("option_a", "Option A", required=True, maxlen=200), F("option_b", "Option B", required=True, maxlen=200),
                        F("option_c", "Option C", required=True, maxlen=200), F("option_d", "Option D", required=True, maxlen=200),
                        F("answer", "Correct answer", "select", True, opts=["a", "b", "c", "d"]), F("explanation", "Explanation", "textarea")]},
}


def audit(action, target=""):
    run("INSERT INTO audit_logs(admin_id, action, target) VALUES (?,?,?)", (g.user["id"], action, target))


def ref_options(kind):
    _, table, col = kind.split(":")
    return [(r["id"], r[col]) for r in q(f"SELECT id, {col} FROM {table} ORDER BY {col}")]    # table/col from ENTITIES config only


def parse(ent, form):
    """Validate form against field specs. Returns (values dict, errors list)."""
    vals, errs = {}, []
    for f in ent["fields"]:
        raw = form.get(f["name"], "").strip()
        k = f["kind"]
        if k == "bool":
            vals[f["name"]] = 1 if form.get(f["name"]) else 0
            continue
        if not raw:
            if f["required"]:
                errs.append(f"{f['label']} is required.")
            vals[f["name"]] = None if k in ("int", "float") or k.startswith("ref") else ""
            continue
        try:
            if k == "int":
                vals[f["name"]] = int(raw)
            elif k == "float":
                vals[f["name"]] = float(raw)
            elif k.startswith("ref"):
                vals[f["name"]] = int(raw)
            elif k == "url":
                if not raw.startswith(("http://", "https://")):
                    errs.append(f"{f['label']} must start with http:// or https://")
                vals[f["name"]] = raw[:f["maxlen"]]
            elif k == "select":
                if raw not in (f["opts"] or []):
                    errs.append(f"{f['label']} has an invalid value.")
                vals[f["name"]] = int(raw) if f["name"] == "difficulty" else raw
            else:
                vals[f["name"]] = raw[:f["maxlen"] if k == "text" else 4000]
        except ValueError:
            errs.append(f"{f['label']} must be a number.")
    return vals, errs


@bp.before_request
def guard():
    if g.user is None:
        return redirect(url_for("auth.login", next=request.path))
    if g.user["role"] != "admin":
        abort(403)


# ------------------------------------------------------------ dashboard & analytics
@bp.route("/")
def dashboard():
    s = {
        "users": scalar("SELECT COUNT(*) FROM users WHERE role='student'"),
        "active_users": scalar("SELECT COUNT(DISTINCT user_id) FROM study_sessions WHERE day >= date('now','-7 day')"),
        "onboarded": scalar("SELECT COUNT(*) FROM profiles WHERE onboarded=1"),
        "resources": scalar("SELECT COUNT(*) FROM resources"),
        "unverified": scalar("SELECT COUNT(*) FROM resources WHERE status='unverified' OR last_verified_at IS NULL"),
        "open_reports": scalar("SELECT COUNT(*) FROM reports WHERE status='open'"),
        "clicks": scalar("SELECT COUNT(*) FROM resource_clicks"),
        "free_clicks": scalar("SELECT COUNT(*) FROM resource_clicks WHERE pricing='free'"),
        "paid_clicks": scalar("SELECT COUNT(*) FROM resource_clicks WHERE pricing IN ('paid','freemium')"),
        "aff_clicks": scalar("SELECT COUNT(*) FROM affiliate_clicks"),
        "conversions": scalar("SELECT COUNT(*) FROM affiliate_clicks WHERE converted=1"),
        "commission": scalar("SELECT SUM(commission_inr) FROM affiliate_clicks WHERE converted=1"),
        "roadmap_users": scalar("SELECT COUNT(*) FROM profiles WHERE career_id IS NOT NULL"),
        "returning": scalar("SELECT COUNT(DISTINCT user_id) FROM (SELECT user_id, COUNT(DISTINCT day) d FROM study_sessions GROUP BY user_id HAVING d>=3)"),
        "feedback_yes": scalar("SELECT COUNT(*) FROM recommendation_feedback WHERE useful=1"),
        "feedback_no": scalar("SELECT COUNT(*) FROM recommendation_feedback WHERE useful=0"),
        "reviews": scalar("SELECT COUNT(*) FROM resource_reviews"),
    }
    data = {
        "streams": q("SELECT s.name, COUNT(*) n FROM profiles p JOIN streams s ON s.id=p.stream_id GROUP BY s.id ORDER BY n DESC LIMIT 6"),
        "careers": q("SELECT c.title name, COUNT(*) n FROM profiles p JOIN careers c ON c.id=p.career_id GROUP BY c.id ORDER BY n DESC LIMIT 6"),
        "skills": q("SELECT s.name, COUNT(*) n FROM user_skills us JOIN skills s ON s.id=us.skill_id WHERE us.level>0 GROUP BY s.id ORDER BY n DESC LIMIT 6"),
        "searches": q("SELECT query name, COUNT(*) n FROM search_log GROUP BY query ORDER BY n DESC LIMIT 8"),
        "top_resources": q("SELECT r.id, r.title name, COUNT(*) n FROM resource_clicks c JOIN resources r ON r.id=c.resource_id GROUP BY r.id ORDER BY n DESC LIMIT 6"),
        "broken": q("SELECT id, title, url FROM resources WHERE status IN ('broken','outdated') LIMIT 10"),
        "no_results": q("SELECT query name, COUNT(*) n FROM search_log WHERE results=0 GROUP BY query ORDER BY n DESC LIMIT 5"),
    }
    return render_template("admin/dashboard.html", s=s, d=data)


# ------------------------------------------------------------ generic CRUD
@bp.route("/e/<name>")
def e_list(name):
    ent = ENTITIES.get(name) or abort(404)
    text = request.args.get("q", "").strip()[:60]
    first = ent["list"][0]
    if text:
        rows = q(f"SELECT * FROM {ent['table']} WHERE {first} LIKE ? ORDER BY id DESC LIMIT 200", (f"%{text}%",))
    else:
        rows = q(f"SELECT * FROM {ent['table']} ORDER BY id DESC LIMIT 200")
    return render_template("admin/list.html", name=name, ent=ent, rows=rows, text=text)


@bp.route("/e/<name>/new", methods=["GET", "POST"])
@bp.route("/e/<name>/<int:eid>", methods=["GET", "POST"])
def e_edit(name, eid=None):
    ent = ENTITIES.get(name) or abort(404)
    row = q1(f"SELECT * FROM {ent['table']} WHERE id=?", (eid,)) if eid else None
    if eid and not row:
        abort(404)
    refs = {f["name"]: ref_options(f["kind"]) for f in ent["fields"] if f["kind"].startswith("ref")}
    all_skills = q("SELECT id, name FROM skills ORDER BY name") if ent.get("m2m") else []
    chosen = set()
    if row and ent.get("m2m"):
        tbl, col = ent["m2m"]
        chosen = {r["skill_id"] for r in q(f"SELECT skill_id FROM {tbl} WHERE {col}=?", (eid,))}
    if request.method == "POST":
        vals, errs = parse(ent, request.form)
        if not errs:
            cols = list(vals)
            try:
                db = get_db()
                if row:
                    db.execute(f"UPDATE {ent['table']} SET " + ", ".join(f"{c}=?" for c in cols) + " WHERE id=?",
                               [vals[c] for c in cols] + [eid])
                    new_id = eid
                else:
                    cur = db.execute(f"INSERT INTO {ent['table']}({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                                     [vals[c] for c in cols])
                    new_id = cur.lastrowid
                if ent.get("m2m"):
                    tbl, col = ent["m2m"]
                    db.execute(f"DELETE FROM {tbl} WHERE {col}=?", (new_id,))
                    ids = {int(x) for x in request.form.getlist("skill_ids") if x.isdigit()}
                    db.executemany(f"INSERT OR IGNORE INTO {tbl}({col}, skill_id) VALUES (?,?)",
                                   [(new_id, i) for i in ids if q1("SELECT 1 FROM skills WHERE id=?", (i,))])
                db.commit()
                audit(("update " if row else "create ") + name, str(new_id))
                flash("Saved.", "ok")
                return redirect(url_for("admin.e_list", name=name))
            except sqlite3.IntegrityError as ex:
                get_db().rollback()
                errs.append(f"Could not save (duplicate or invalid reference): {ex}")
        for e in errs:
            flash(e, "error")
        return render_template("admin/edit.html", name=name, ent=ent, row=request.form, eid=eid, refs=refs,
                               all_skills=all_skills, chosen=chosen), 400
    return render_template("admin/edit.html", name=name, ent=ent, row=dict(row) if row else {}, eid=eid, refs=refs,
                           all_skills=all_skills, chosen=chosen)


@bp.route("/e/<name>/<int:eid>/delete", methods=["POST"])
def e_delete(name, eid):
    ent = ENTITIES.get(name) or abort(404)
    try:
        run(f"DELETE FROM {ent['table']} WHERE id=?", (eid,))
        audit("delete " + name, str(eid))
        flash("Deleted.", "ok")
    except sqlite3.IntegrityError:
        flash("This item is still referenced by other records.", "error")
    return redirect(url_for("admin.e_list", name=name))


# ------------------------------------------------------------ resource verification
@bp.route("/resources/<int:rid>/verify", methods=["POST"])
def verify(rid):
    status = request.form.get("status", "active")
    if status not in ("active", "broken", "outdated", "hidden", "unverified") or not q1("SELECT 1 FROM resources WHERE id=?", (rid,)):
        abort(400)
    run("UPDATE resources SET status=?, last_verified_at=?, verification_notes=? WHERE id=?",
        (status, date.today().isoformat(), request.form.get("notes", "").strip()[:300], rid))
    audit("verify resource", f"{rid}:{status}")
    flash("Verification recorded (manual check by admin).", "ok")
    return redirect(request.referrer or url_for("admin.e_list", name="resources"))


# ------------------------------------------------------------ users
@bp.route("/users")
def users():
    text = request.args.get("q", "").strip()[:60]
    like = f"%{text.lower()}%"
    rows = q("""SELECT u.*, p.onboarded, (SELECT COALESCE(SUM(minutes),0) FROM study_sessions WHERE user_id=u.id) minutes
                FROM users u LEFT JOIN profiles p ON p.user_id=u.id
                WHERE lower(u.email) LIKE ? OR lower(u.name) LIKE ? ORDER BY u.created_at DESC LIMIT 200""", (like, like))
    return render_template("admin/users.html", rows=rows, text=text)


@bp.route("/users/<int:uid>/toggle", methods=["POST"])
def user_toggle(uid):
    u = q1("SELECT * FROM users WHERE id=?", (uid,))
    if not u:
        abort(404)
    if uid == g.user["id"]:
        flash("You cannot deactivate your own account.", "error")
    else:
        run("UPDATE users SET is_active=1-is_active WHERE id=?", (uid,))
        audit("toggle user", str(uid))
    return redirect(url_for("admin.users"))


# ------------------------------------------------------------ reports, affiliates, feedback
@bp.route("/reports", methods=["GET", "POST"])
def reports():
    if request.method == "POST":
        rid, action = request.form.get("id", ""), request.form.get("action")
        if rid.isdigit() and action in ("resolved", "dismissed", "open"):
            run("UPDATE reports SET status=? WHERE id=?", (action, int(rid)))
            audit("report " + action, rid)
        return redirect(url_for("admin.reports"))
    rows = q("SELECT rp.*, r.title, r.status rstatus, u.email FROM reports rp JOIN resources r ON r.id=rp.resource_id "
             "LEFT JOIN users u ON u.id=rp.user_id ORDER BY rp.status='open' DESC, rp.created_at DESC LIMIT 200")
    return render_template("admin/reports.html", rows=rows)


@bp.route("/affiliates", methods=["GET", "POST"])
def affiliates():
    if request.method == "POST":
        cid, action = request.form.get("id", ""), request.form.get("action")
        if cid.isdigit() and action == "convert":
            try:
                amount = max(0.0, float(request.form.get("commission", "0")))
            except ValueError:
                amount = 0.0
            run("UPDATE affiliate_clicks SET converted=1, commission_inr=? WHERE id=?", (amount, int(cid)))
            audit("affiliate conversion recorded", cid)
        return redirect(url_for("admin.affiliates"))
    rows = q("""SELECT r.id, r.title, r.affiliate_url, r.affiliate_ref, r.commission_pct, r.pricing,
                (SELECT COUNT(*) FROM affiliate_clicks a WHERE a.resource_id=r.id) clicks,
                (SELECT COUNT(*) FROM affiliate_clicks a WHERE a.resource_id=r.id AND converted=1) conv,
                (SELECT COALESCE(SUM(commission_inr),0) FROM affiliate_clicks a WHERE a.resource_id=r.id AND converted=1) revenue
                FROM resources r WHERE r.affiliate_url != '' OR r.pricing='paid' ORDER BY clicks DESC""")
    clicks = q("SELECT a.*, r.title FROM affiliate_clicks a JOIN resources r ON r.id=a.resource_id ORDER BY a.created_at DESC LIMIT 30")
    return render_template("admin/affiliates.html", rows=rows, clicks=clicks)


@bp.route("/feedback")
def feedback():
    fb = q("SELECT reason, useful, COUNT(*) n FROM recommendation_feedback GROUP BY reason, useful ORDER BY n DESC")
    reviews = q("SELECT rv.*, r.title, u.name FROM resource_reviews rv JOIN resources r ON r.id=rv.resource_id "
                "JOIN users u ON u.id=rv.user_id ORDER BY rv.created_at DESC LIMIT 50")
    return render_template("admin/feedback.html", fb=fb, reviews=reviews)


@bp.route("/audit")
def audit_log():
    return render_template("admin/audit.html", rows=q(
        "SELECT a.*, u.email FROM audit_logs a LEFT JOIN users u ON u.id=a.admin_id ORDER BY a.id DESC LIMIT 100"))
