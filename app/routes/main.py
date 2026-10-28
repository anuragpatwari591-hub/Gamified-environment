"""Public pages: landing, catalogue (streams/careers/skills/resources), discovery mode, legal, SEO."""
from datetime import date

from flask import (Blueprint, Response, abort, flash, g, redirect, render_template, request, url_for)

from ..db import q, q1, run, scalar
from ..recommendation import engine
from ..security import login_required, rate_limited
from ..services import core

bp = Blueprint("main", __name__)

DISCOVER_QUESTIONS = [
    ("On a free weekend you would rather...", [
        ("Build a small app or tool", "build,web"), ("Dig into data and look for patterns", "data,research"),
        ("Work out how systems get attacked and defended", "security,systems"),
        ("Design something that looks great", "design,web"), ("Plan a campaign or a small business", "business,people"),
        ("Work through numbers and budgets", "money,exams")]),
    ("Which school subject felt most natural?", [
        ("Maths and logic", "data,ai,money"), ("Computers", "build,security,systems"),
        ("Languages and communication", "people,writing,business"), ("Art and design", "design"),
        ("Commerce or social science", "money,business,law")]),
    ("You prefer work that is...", [
        ("Solving puzzles on your own", "build,security,research"), ("Done with and for people", "people,business"),
        ("Structured, rule-based and accurate", "money,law,exams"), ("Creative and open-ended", "design,writing")]),
    ("How comfortable are you with programming today?", [
        ("Not at all", "business,money,design,law,people"), ("A little", "data,web"), ("Very comfortable", "build,ai,security,systems")]),
    ("What matters most to you in the long run?", [
        ("A recognised professional qualification", "exams,law,money"), ("Starting something of my own", "business,build"),
        ("Deep research and new ideas", "research,ai"), ("Working in the technology industry", "build,data,security,web")]),
    ("Which topic sounds most exciting?", [
        ("AI that learns from data", "ai,data"), ("Keeping systems safe", "security"),
        ("Websites and apps", "web,build"), ("Accounts, tax and markets", "money"), ("Brands and customers", "business,people")]),
    ("How much time can you study each day?", [
        ("About 30 minutes", ""), ("About 1 hour", ""), ("2 hours or more", "")]),
]


@bp.route("/")
def home():
    stats = {
        "resources": scalar("SELECT COUNT(*) FROM resources WHERE status!='hidden'"),
        "free": scalar("SELECT COUNT(*) FROM resources WHERE pricing='free' AND status!='hidden'"),
        "careers": scalar("SELECT COUNT(*) FROM careers"), "skills": scalar("SELECT COUNT(*) FROM skills"),
        "projects": scalar("SELECT COUNT(*) FROM projects"), "streams": scalar("SELECT COUNT(*) FROM streams"),
    }
    streams = q("SELECT * FROM streams ORDER BY group_name, name")
    return render_template("home.html", stats=stats, streams=streams,
                           careers=q("SELECT * FROM careers ORDER BY title LIMIT 6"),
                           sponsored=q("SELECT * FROM sponsored_content WHERE active=1 LIMIT 2"))


# ------------------------------------------------------------ catalogue
@bp.route("/streams")
def streams():
    return render_template("streams.html", streams=q("SELECT * FROM streams ORDER BY group_name, name"))


@bp.route("/streams/<slug>")
def stream_detail(slug):
    s = q1("SELECT * FROM streams WHERE slug=?", (slug,))
    if not s:
        abort(404)
    return render_template("stream.html", s=s, careers=q("SELECT * FROM careers ORDER BY title"))


@bp.route("/careers")
def careers():
    return render_template("careers.html", careers=q("SELECT * FROM careers ORDER BY title"))


@bp.route("/careers/<slug>")
def career_detail(slug):
    c = q1("SELECT * FROM careers WHERE slug=?", (slug,))
    if not c:
        abort(404)
    skills = q("SELECT s.*, cs.required_level FROM career_skills cs JOIN skills s ON s.id=cs.skill_id "
               "WHERE cs.career_id=? ORDER BY cs.required_level DESC", (c["id"],))
    rm = q1("SELECT * FROM roadmaps WHERE career_id=?", (c["id"],))
    stages = q("SELECT st.*, sk.name skill_name, sk.slug skill_slug FROM roadmap_stages st LEFT JOIN skills sk ON sk.id=st.skill_id "
               "WHERE roadmap_id=? ORDER BY position", (rm["id"],)) if rm else []
    free_res = q("SELECT DISTINCT r.* FROM resources r JOIN resource_skills rs ON rs.resource_id=r.id "
                 "JOIN career_skills cs ON cs.skill_id=rs.skill_id WHERE cs.career_id=? AND r.pricing='free' "
                 "AND r.status!='hidden' LIMIT 6", (c["id"],))
    paid_res = q("SELECT DISTINCT r.* FROM resources r JOIN resource_skills rs ON rs.resource_id=r.id "
                 "JOIN career_skills cs ON cs.skill_id=rs.skill_id WHERE cs.career_id=? AND r.pricing IN ('paid','freemium') "
                 "AND r.status!='hidden' LIMIT 4", (c["id"],))
    projects = q("SELECT DISTINCT p.* FROM projects p JOIN project_skills ps ON ps.project_id=p.id "
                 "JOIN career_skills cs ON cs.skill_id=ps.skill_id WHERE cs.career_id=? ORDER BY p.difficulty", (c["id"],))
    return render_template("career.html", c=c, skills=skills, rm=rm, stages=stages, free_res=free_res,
                           paid_res=paid_res, projects=projects)


@bp.route("/skills")
def skills():
    rows = q("SELECT s.*, (SELECT COUNT(*) FROM resource_skills rs WHERE rs.skill_id=s.id) n FROM skills s ORDER BY category, name")
    return render_template("skills.html", skills=rows)


@bp.route("/skills/<slug>")
def skill_detail(slug):
    s = q1("SELECT * FROM skills WHERE slug=?", (slug,))
    if not s:
        abort(404)
    res = q("SELECT r.* FROM resources r JOIN resource_skills rs ON rs.resource_id=r.id WHERE rs.skill_id=? "
            "AND r.status!='hidden' ORDER BY (r.pricing='free') DESC, r.difficulty", (s["id"],))
    projects = q("SELECT p.* FROM projects p JOIN project_skills ps ON ps.project_id=p.id WHERE ps.skill_id=? ORDER BY difficulty", (s["id"],))
    careers = q("SELECT c.* FROM careers c JOIN career_skills cs ON cs.career_id=c.id WHERE cs.skill_id=?", (s["id"],))
    return render_template("skill.html", s=s, res=res, projects=projects, careers=careers)


# ------------------------------------------------------------ resources
@bp.route("/resources")
def resources():
    a = request.args
    text = a.get("q", "").strip()[:80]
    rows = core.search_resources(text, a.get("pricing", ""), a.get("difficulty", ""), a.get("language", ""),
                                 a.get("format", ""), a.get("category", ""), a.get("provider", ""),
                                 a.get("max_minutes", ""), a.get("min_rating", ""), a.get("sort", ""))
    if text:
        run("INSERT INTO search_log(query, results, user_id) VALUES (?,?,?)",
            (text.lower(), len(rows), g.user["id"] if g.user else None))
    ranked = None
    if g.user and rows:
        ctx = core.build_context(g.user["id"])
        by_id = {x["resource"]["id"]: x for x in engine.rank(rows, ctx, limit=len(rows), exclude_completed=False,
                                                              min_free_alternative=False)}
        ranked = by_id
        if a.get("sort", "") in ("", "relevance", "match"):
            rows = sorted(rows, key=lambda r: -by_id[r["id"]]["score"])
    facets = {
        "categories": [r[0] for r in q("SELECT DISTINCT category FROM resources WHERE status!='hidden' ORDER BY 1")],
        "providers": [r[0] for r in q("SELECT DISTINCT provider FROM resources WHERE status!='hidden' ORDER BY 1")],
        "languages": [r[0] for r in q("SELECT DISTINCT language FROM resources WHERE status!='hidden' ORDER BY 1")],
    }
    # Related non-resource hits so search spans skills, careers, projects
    related = {}
    if text:
        like = f"%{text.lower()}%"
        related = {
            "skills": q("SELECT slug, name FROM skills WHERE lower(name) LIKE ? LIMIT 5", (like,)),
            "careers": q("SELECT slug, title FROM careers WHERE lower(title) LIKE ? OR lower(description) LIKE ? LIMIT 5", (like, like)),
            "projects": q("SELECT id, title FROM projects WHERE lower(title) LIKE ? OR lower(technologies) LIKE ? LIMIT 5", (like, like)),
        }
    sponsored = q("SELECT * FROM sponsored_content WHERE active=1 LIMIT 1") if not text else []
    return render_template("resources.html", rows=rows, ranked=ranked, facets=facets, a=a, text=text,
                           related=related, sponsored=sponsored, formats=core.FORMATS, diff=core.DIFF)


@bp.route("/resources/<int:rid>")
def resource_detail(rid):
    r = core.get_resource(rid)
    if not r or r["status"] == "hidden":
        abort(404)
    skills = q("SELECT s.* FROM skills s JOIN resource_skills rs ON rs.skill_id=s.id WHERE rs.resource_id=?", (rid,))
    qual = engine.quality(r, community=r["community"])
    why = ranked = None
    if g.user:
        ctx = core.build_context(g.user["id"])
        ctx["resources_by_id"] = {rid: r}
        ranked = engine.score_resource(r, ctx)
        why = engine.explain(r, ranked, ctx)
    free_alts = []
    if r["pricing"] == "paid" and r["skill_ids"]:
        free_alts = [x for x in core.all_resources() if x["pricing"] == "free" and x["skill_ids"] & r["skill_ids"]][:3]
    reviews = q("SELECT rv.*, u.name FROM resource_reviews rv JOIN users u ON u.id=rv.user_id WHERE resource_id=? AND rv.review!='' "
                "ORDER BY created_at DESC LIMIT 5", (rid,))
    mine = prog = saved = None
    if g.user:
        mine = q1("SELECT * FROM resource_reviews WHERE user_id=? AND resource_id=?", (g.user["id"], rid))
        prog = q1("SELECT * FROM learning_progress WHERE user_id=? AND resource_id=?", (g.user["id"], rid))
        saved = q1("SELECT * FROM bookmarks WHERE user_id=? AND kind='resource' AND ref_id=?", (g.user["id"], rid))
    return render_template("resource.html", r=r, skills=skills, qual=qual, why=why, ranked=ranked, free_alts=free_alts,
                           reviews=reviews, mine=mine, prog=prog, saved=saved, diff=core.DIFF, folders=core.FOLDERS,
                           reasons=core.FEEDBACK_REASONS, today=date.today().isoformat())


@bp.route("/go/<int:rid>")
def go(rid):
    """Outbound click: logged for analytics, and routed via the affiliate link when one is configured."""
    r = q1("SELECT * FROM resources WHERE id=? AND status!='hidden'", (rid,))
    if not r:
        abort(404)
    uid = g.user["id"] if g.user else None
    run("INSERT INTO resource_clicks(resource_id, user_id, pricing) VALUES (?,?,?)", (rid, uid, r["pricing"]))
    target = r["url"]
    if r["affiliate_url"].startswith(("http://", "https://")):
        run("INSERT INTO affiliate_clicks(resource_id, user_id, ref_id) VALUES (?,?,?)", (rid, uid, r["affiliate_ref"]))
        target = r["affiliate_url"]
    if uid:
        run("INSERT OR IGNORE INTO learning_progress(user_id, resource_id) VALUES (?,?)", (uid, rid))
    return redirect(target)


@bp.route("/compare")
def compare():
    ids = [int(x) for x in request.args.getlist("id") if x.isdigit()][:3]
    items = [core.get_resource(i) for i in ids]
    items = [r for r in items if r and r["status"] != "hidden"]
    return render_template("compare.html", items=items, diff=core.DIFF)


@bp.route("/resources/<int:rid>/report", methods=["POST"])
def report(rid):
    if not q1("SELECT 1 FROM resources WHERE id=?", (rid,)):
        abort(404)
    if rate_limited(f"report:{request.remote_addr}", 10, 3600):
        abort(429)
    kind = request.form.get("kind", "")
    if kind not in ("broken_link", "outdated", "misleading", "wrong_category", "wrong_price"):
        flash("Please choose what is wrong with the resource.", "error")
        return redirect(url_for("main.resource_detail", rid=rid))
    run("INSERT INTO reports(resource_id, user_id, kind, note) VALUES (?,?,?,?)",
        (rid, g.user["id"] if g.user else None, kind, request.form.get("note", "").strip()[:500]))
    flash("Thanks - an admin will review your report.", "ok")
    return redirect(url_for("main.resource_detail", rid=rid))


# ------------------------------------------------------------ discovery mode
@bp.route("/discover", methods=["GET", "POST"])
def discover():
    if request.method == "GET":
        return render_template("discover.html", questions=DISCOVER_QUESTIONS, results=None)
    tags = {}
    for i, (_, opts) in enumerate(DISCOVER_QUESTIONS):
        v = request.form.get(f"q{i}", "")
        if v.isdigit() and int(v) < len(opts):
            for t in opts[int(v)][1].split(","):
                if t:
                    tags[t] = tags.get(t, 0) + 1
    if not tags:
        flash("Answer at least one question so we have something to work with.", "error")
        return render_template("discover.html", questions=DISCOVER_QUESTIONS, results=None), 400
    scored = []
    for c in q("SELECT * FROM careers"):
        ct = [t for t in c["interest_tags"].split(",") if t]
        matched = [t for t in ct if t in tags]
        s = sum(tags[t] for t in matched) / max(1, len(ct)) ** 0.5
        if matched:
            scored.append((s, c, matched))
    scored.sort(key=lambda x: -x[0])
    results = []
    for s, c, matched in scored[:3]:
        first = q1("SELECT st.title FROM roadmap_stages st JOIN roadmaps r ON r.id=st.roadmap_id WHERE r.career_id=? ORDER BY position LIMIT 1", (c["id"],))
        res = q("SELECT DISTINCT r.id, r.title, r.provider FROM resources r JOIN resource_skills rs ON rs.resource_id=r.id "
                "JOIN roadmap_stages st ON st.skill_id=rs.skill_id JOIN roadmaps m ON m.id=st.roadmap_id "
                "WHERE m.career_id=? AND r.pricing='free' AND r.difficulty=1 AND r.status!='hidden' ORDER BY st.position LIMIT 2", (c["id"],))
        proj = q1("SELECT DISTINCT p.id, p.title FROM projects p JOIN project_skills ps ON ps.project_id=p.id "
                  "JOIN career_skills cs ON cs.skill_id=ps.skill_id WHERE cs.career_id=? ORDER BY p.difficulty LIMIT 1", (c["id"],))
        results.append({"career": c, "matched": matched, "first_stage": first["title"] if first else None,
                        "resources": res, "project": proj})
    return render_template("discover.html", questions=DISCOVER_QUESTIONS, results=results)


# ------------------------------------------------------------ legal & SEO
@bp.route("/privacy")
def privacy():
    return render_template("legal/privacy.html")


@bp.route("/terms")
def terms():
    return render_template("legal/terms.html")


@bp.route("/disclosure")
def disclosure():
    return render_template("legal/disclosure.html")


@bp.route("/robots.txt")
def robots():
    from flask import current_app
    base = current_app.config["SITE_URL"]
    return Response(f"User-agent: *\nDisallow: /admin\nDisallow: /api\nDisallow: /go/\nSitemap: {base}/sitemap.xml\n", mimetype="text/plain")


@bp.route("/sitemap.xml")
def sitemap():
    from flask import current_app
    base = current_app.config["SITE_URL"]
    paths = ["/", "/resources", "/careers", "/skills", "/streams", "/discover", "/privacy", "/terms", "/disclosure"]
    paths += [f"/careers/{r['slug']}" for r in q("SELECT slug FROM careers")]
    paths += [f"/skills/{r['slug']}" for r in q("SELECT slug FROM skills")]
    paths += [f"/streams/{r['slug']}" for r in q("SELECT slug FROM streams")]
    paths += [f"/resources/{r['id']}" for r in q("SELECT id FROM resources WHERE status!='hidden'")]
    xml = ('<?xml version="1.0" encoding="UTF-8"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">' +
           "".join(f"<url><loc>{base}{p}</loc></url>" for p in paths) + "</urlset>")
    return Response(xml, mimetype="application/xml")
