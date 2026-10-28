"""Data-access + domain logic shared by routes. Converts DB rows to the plain dicts the engine expects."""
from datetime import date, timedelta

from ..db import q, q1, run, scalar
from ..recommendation import engine

BUDGETS = {"free": "Completely free", "mostly_free": "Mostly free", "paid_ok": "Open to paid courses",
           "premium": "Premium learning acceptable"}
FORMATS = {"video": "Video", "reading": "Reading", "interactive": "Interactive", "practice": "Practice-first",
           "project": "Project-first"}
INTERESTS = ["Software Development", "AI & Machine Learning", "Cybersecurity", "Data Analytics", "Web Development",
             "Finance", "Accounting & Taxation", "Marketing", "Management", "Design", "Entrepreneurship",
             "Consulting", "Research", "Government Exams", "Law & Compliance"]
LANGUAGES = ["English", "Hindi", "Bengali"]
FEEDBACK_REASONS = {"too_difficult": "Too difficult", "too_long": "Too long", "boring": "Boring",
                    "wrong_topic": "Wrong topic", "already_knew": "Already knew this",
                    "wrong_style": "Wrong learning style", "not_relevant": "Not relevant"}
FOLDERS = ["Learn Later", "Projects", "Interview", "Semester", "Career"]
DIFF = {1: "Beginner", 2: "Intermediate", 3: "Advanced"}


# ------------------------------------------------------------ resources
def _res_dict(row, skills_map, community_map):
    d = dict(row)
    d["skill_ids"] = skills_map.get(d["id"], set())
    d["community"] = community_map.get(d["id"])
    return d


def all_resources(include_hidden=False):
    rows = q("SELECT * FROM resources" + ("" if include_hidden else " WHERE status != 'hidden'"))
    sm = {}
    for r in q("SELECT resource_id, skill_id FROM resource_skills"):
        sm.setdefault(r["resource_id"], set()).add(r["skill_id"])
    cm = {r["resource_id"]: (r["a"], r["n"]) for r in q(
        "SELECT resource_id, AVG(rating) a, COUNT(*) n FROM resource_reviews GROUP BY resource_id")}
    return [_res_dict(r, sm, cm) for r in rows]


def get_resource(rid):
    row = q1("SELECT * FROM resources WHERE id=?", (rid,))
    if not row:
        return None
    sm = {rid: {r["skill_id"] for r in q("SELECT skill_id FROM resource_skills WHERE resource_id=?", (rid,))}}
    c = q1("SELECT AVG(rating) a, COUNT(*) n FROM resource_reviews WHERE resource_id=?", (rid,))
    cm = {rid: (c["a"], c["n"])} if c and c["n"] else {}
    return _res_dict(row, sm, cm)


def search_resources(text="", pricing="", difficulty="", language="", fmt="", category="", provider="",
                     max_minutes="", min_rating="", sort="relevance", limit=60):
    """Filtered search. All values are bound parameters; unknown filter values simply yield no filter."""
    sql = ["SELECT DISTINCT r.* FROM resources r LEFT JOIN resource_skills rs ON rs.resource_id=r.id "
           "LEFT JOIN skills s ON s.id=rs.skill_id WHERE r.status NOT IN ('hidden','broken')"]
    a = []
    text = (text or "").strip()[:80]
    if text:
        like = f"%{text.lower()}%"
        sql.append("AND (lower(r.title) LIKE ? OR lower(r.provider) LIKE ? OR lower(r.topic) LIKE ? "
                   "OR lower(r.tags) LIKE ? OR lower(r.description) LIKE ? OR lower(s.name) LIKE ?)")
        a += [like] * 6
    if pricing in ("free", "paid", "freemium"):
        sql.append("AND r.pricing=?")
        a.append(pricing)
    if difficulty in ("1", "2", "3"):
        sql.append("AND r.difficulty=?")
        a.append(int(difficulty))
    if language:
        sql.append("AND r.language=?")
        a.append(language)
    if fmt in FORMATS:
        sql.append("AND r.format=?")
        a.append(fmt)
    if category:
        sql.append("AND r.category=?")
        a.append(category)
    if provider:
        sql.append("AND r.provider=?")
        a.append(provider)
    if str(max_minutes).isdigit():
        sql.append("AND r.duration_min IS NOT NULL AND r.duration_min<=?")
        a.append(int(max_minutes))
    try:
        mr = float(min_rating) if min_rating else None
    except ValueError:
        mr = None                      # invalid number: ignore the filter rather than fail
    if mr is not None:
        sql.append("AND r.rating IS NOT NULL AND r.rating>=?")
        a.append(mr)
    order = {"duration": "r.duration_min IS NULL, r.duration_min", "difficulty": "r.difficulty",
             "newest": "r.created_at DESC"}.get(sort, "r.title")
    sql.append(f"ORDER BY {order} LIMIT ?")      # `order` comes from a fixed whitelist above, never user text
    a.append(limit)
    rows = q(" ".join(sql), a)
    ids = [r["id"] for r in rows]
    if not ids:
        return []
    sm = {}
    for r in q("SELECT resource_id, skill_id FROM resource_skills"):
        sm.setdefault(r["resource_id"], set()).add(r["skill_id"])
    return [_res_dict(r, sm, {}) for r in rows]


# ------------------------------------------------------------ context & roadmap
def get_profile(uid):
    return q1("SELECT p.*, s.name stream_name, c.title career_title FROM profiles p "
              "LEFT JOIN streams s ON s.id=p.stream_id LEFT JOIN careers c ON c.id=p.career_id WHERE p.user_id=?", (uid,))


def user_skill_levels(uid):
    return {r["skill_id"]: r["level"] for r in q("SELECT skill_id, level FROM user_skills WHERE user_id=?", (uid,))}


def roadmap_stages(uid, career_id):
    """Ordered stages with a 'done' flag: done = manually completed OR skill level reached target."""
    if not career_id:
        return None, []
    rm = q1("SELECT * FROM roadmaps WHERE career_id=?", (career_id,))
    if not rm:
        return None, []
    levels = user_skill_levels(uid)
    manual = {r["stage_id"] for r in q("SELECT stage_id FROM user_stages WHERE user_id=?", (uid,))}
    out = []
    for s in q("SELECT st.*, sk.name skill_name FROM roadmap_stages st LEFT JOIN skills sk ON sk.id=st.skill_id "
               "WHERE roadmap_id=? ORDER BY position", (rm["id"],)):
        d = dict(s)
        d["level"] = levels.get(s["skill_id"], 0) if s["skill_id"] else 0
        d["done"] = s["id"] in manual or (s["skill_id"] is not None and d["level"] >= s["target_level"])
        d["pct"] = 100 if d["done"] else min(99, round(100 * d["level"] / max(1, s["target_level"])))
        out.append(d)
    return rm, out


def build_context(uid):
    prof = get_profile(uid)
    if prof is None:
        return engine.make_context()
    rm, stages = roadmap_stages(uid, prof["career_id"])
    cs = {r["skill_id"]: r["required_level"] for r in q(
        "SELECT skill_id, required_level FROM career_skills WHERE career_id=?", (prof["career_id"],))} if prof["career_id"] else {}
    fb = [dict(r) for r in q("SELECT resource_id, useful, reason FROM recommendation_feedback WHERE user_id=?", (uid,))]
    levels = user_skill_levels(uid)
    # "already knew this" feedback raises the assumed level of that resource's skills (learning loop)
    for r in fb:
        if r["reason"] == "already_knew" and not r["useful"]:
            for s in q("SELECT skill_id FROM resource_skills WHERE resource_id=?", (r["resource_id"],)):
                levels[s["skill_id"]] = max(levels.get(s["skill_id"], 0), 40)
    current = next((s for s in stages if not s["done"]), None)
    return engine.make_context(
        career_id=prof["career_id"], career_title=prof["career_title"], career_skills=cs,
        interests=[r["interest"] for r in q("SELECT interest FROM user_interests WHERE user_id=?", (uid,))],
        formats={r["format"] for r in q("SELECT format FROM user_formats WHERE user_id=?", (uid,))},
        level={"beginner": 1, "intermediate": 2, "advanced": 3}[prof["level"]],
        minutes_per_day=prof["minutes_per_day"], language=prof["language"], budget=prof["budget"],
        free_first=bool(prof["free_first"]), skill_levels=levels,
        focus_skill_ids={current["skill_id"]} if current and current["skill_id"] else set(),
        roadmap_order=[(s["skill_id"], s["target_level"]) for s in stages if s["skill_id"]],
        completed={r["resource_id"] for r in q(
            "SELECT resource_id FROM learning_progress WHERE user_id=? AND status='completed'", (uid,))},
        feedback=fb)


def get_next_move(uid):
    prof = get_profile(uid)
    ctx = build_context(uid)
    _, stages = roadmap_stages(uid, prof["career_id"] if prof else None)
    projects = {}
    for p in q("SELECT p.*, ps.skill_id FROM projects p JOIN project_skills ps ON ps.project_id=p.id ORDER BY p.difficulty DESC"):
        projects[p["skill_id"]] = dict(p)
    if not stages:
        ranked = engine.rank(all_resources(), ctx, limit=3)
        top = ranked[0] if ranked else None
        return {"kind": "choose", "title": "Pick a career goal to unlock your roadmap",
                "reason": "NAVORA needs a target career to build your learning order. Until then, here are strong general matches.",
                "minutes": ctx["minutes_per_day"], "resource": top, "alternatives": ranked[1:],
                "outcome": "A personalised roadmap.", "after": "Choose a career in your profile.", "stage": None}
    return engine.next_move(ctx, stages, all_resources(), projects)


def skill_gap(uid):
    prof = get_profile(uid)
    if not prof or not prof["career_id"]:
        return []
    levels = user_skill_levels(uid)
    rows = q("SELECT cs.required_level, s.id, s.name, s.slug FROM career_skills cs JOIN skills s ON s.id=cs.skill_id "
             "WHERE cs.career_id=?", (prof["career_id"],))
    order = {s["skill_id"]: s["position"] for s in q(
        "SELECT st.skill_id, st.position FROM roadmap_stages st JOIN roadmaps r ON r.id=st.roadmap_id "
        "WHERE r.career_id=? AND st.skill_id IS NOT NULL", (prof["career_id"],))}
    out = []
    for r in rows:
        cur = levels.get(r["id"], 0)
        out.append({"skill_id": r["id"], "name": r["name"], "slug": r["slug"], "current": cur,
                    "required": r["required_level"], "gap": max(0, r["required_level"] - cur),
                    "position": order.get(r["id"], 99)})
    out.sort(key=lambda x: (x["gap"] == 0, x["position"]))
    return out


# ------------------------------------------------------------ activity
def level_label(v):
    return "Not started" if v < 5 else "Beginner" if v < 35 else "Intermediate" if v < 70 else "Advanced"


def bump_skills(uid, resource_id, amount):
    for s in q("SELECT skill_id FROM resource_skills WHERE resource_id=?", (resource_id,)):
        run("INSERT INTO user_skills(user_id, skill_id, level) VALUES (?,?,?) "
            "ON CONFLICT(user_id, skill_id) DO UPDATE SET level=MIN(100, level+?)", (uid, s["skill_id"], min(amount, 100), amount))


def notify(uid, message, kind="info"):
    run("INSERT INTO notifications(user_id, kind, message) VALUES (?,?,?)", (uid, kind, message))


def complete_resource(uid, rid):
    res = q1("SELECT * FROM resources WHERE id=?", (rid,))
    if not res:
        return False
    already = q1("SELECT status FROM learning_progress WHERE user_id=? AND resource_id=?", (uid, rid))
    run("INSERT INTO learning_progress(user_id, resource_id, status, completed_at) VALUES (?,?, 'completed', datetime('now')) "
        "ON CONFLICT(user_id, resource_id) DO UPDATE SET status='completed', completed_at=datetime('now')", (uid, rid))
    if not (already and already["status"] == "completed"):
        # Heuristic progress estimate, not an assessment: harder resources move the skill bar more.
        bump_skills(uid, rid, {1: 15, 2: 12, 3: 10}[res["difficulty"]])
        notify(uid, f"You completed \"{res['title']}\". Nice work - check your Next Move.", "milestone")
        check_stage_milestones(uid)
    return True


def check_stage_milestones(uid):
    prof = get_profile(uid)
    if not prof or not prof["career_id"]:
        return
    _, stages = roadmap_stages(uid, prof["career_id"])
    for s in stages:
        if s["done"]:
            msg = f"Roadmap milestone reached: {s['title']}"
            if not q1("SELECT 1 FROM notifications WHERE user_id=? AND message=?", (uid, msg)):
                notify(uid, msg, "milestone")


def log_session(uid, minutes, topic="", resource_id=None, day=None):
    run("INSERT INTO study_sessions(user_id, resource_id, topic, minutes, day) VALUES (?,?,?,?,?)",
        (uid, resource_id, topic[:80], minutes, day or date.today().isoformat()))


def week_minutes(uid):
    start = (date.today() - timedelta(days=date.today().weekday())).isoformat()
    return scalar("SELECT SUM(minutes) FROM study_sessions WHERE user_id=? AND day>=?", (uid, start))


def daily_minutes(uid, days=7):
    today = date.today()
    rows = {r["day"]: r["m"] for r in q("SELECT day, SUM(minutes) m FROM study_sessions WHERE user_id=? AND day>=? GROUP BY day",
                                       (uid, (today - timedelta(days=days - 1)).isoformat()))}
    return [((today - timedelta(days=i)), rows.get((today - timedelta(days=i)).isoformat(), 0))
            for i in range(days - 1, -1, -1)]


def streak(uid):
    days = {r["day"] for r in q("SELECT DISTINCT day FROM study_sessions WHERE user_id=?", (uid,))}
    d, n = date.today(), 0
    if d.isoformat() not in days:           # a missed "today" does not break yesterday's streak yet
        d -= timedelta(days=1)
    while d.isoformat() in days:
        n += 1
        d -= timedelta(days=1)
    return n


def learning_snapshot(uid):
    prof = get_profile(uid)
    return {
        "week_minutes": week_minutes(uid),
        "goal_minutes": (prof["minutes_per_day"] * 7) if prof else 420,
        "streak": streak(uid),
        "completed": scalar("SELECT COUNT(*) FROM learning_progress WHERE user_id=? AND status='completed'", (uid,)),
        "started": scalar("SELECT COUNT(*) FROM learning_progress WHERE user_id=? AND status='started'", (uid,)),
        "projects_done": scalar("SELECT COUNT(*) FROM user_projects WHERE user_id=? AND status='completed'", (uid,)),
        "total_minutes": scalar("SELECT SUM(minutes) FROM study_sessions WHERE user_id=?", (uid,)),
    }


READINESS_ITEMS = {
    "resume": "Resume written and reviewed by someone you trust",
    "github": "GitHub (or equivalent) profile with at least 2 public projects",
    "portfolio": "Portfolio page or case-study write-ups online",
    "linkedin": "Professional profile (LinkedIn or similar) completed",
    "certification": "At least one relevant certification or verified course completed",
    "internship": "Internship, freelance or volunteer experience",
    "coursework": "Relevant coursework identified and linked to your career goal",
}


def readiness(uid):
    done = {r["item"] for r in q("SELECT item FROM readiness_items WHERE user_id=? AND done=1", (uid,))}
    items = [{"key": k, "label": v, "done": k in done, "auto": False} for k, v in READINESS_ITEMS.items()]
    gap = skill_gap(uid)
    met = sum(1 for g in gap if g["gap"] == 0)
    skills_ok = bool(gap) and met / len(gap) >= 0.6
    items.insert(0, {"key": "skills", "label": f"Core skills for your target role at required level "
                     f"({met}/{len(gap)} met; need 60%)", "done": skills_ok, "auto": True})
    projects = scalar("SELECT COUNT(*) FROM user_projects WHERE user_id=? AND status='completed'", (uid,))
    items.insert(1, {"key": "projects", "label": f"Complete at least 2 projects ({projects} done)", "done": projects >= 2, "auto": True})
    pct = round(100 * sum(1 for i in items if i["done"]) / len(items))
    return items, pct
