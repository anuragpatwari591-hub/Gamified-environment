"""Seed the database: python -m seed.seed   (safe to re-run only on an empty DB; use --reset to wipe)."""
import secrets
import sys
from datetime import date, timedelta

from werkzeug.security import generate_password_hash

from app import create_app
from app.db import get_db, init_db
from seed import data_catalog as C
from seed import data_projects as P
from seed import data_resources as R

DEMO_EMAIL = "demo@navora.local"
DEMO_PASSWORD = "DemoStudent#2026"      # demo account only; documented in README


def seed_catalog(db):
    db.executemany("INSERT INTO streams(slug, name, group_name) VALUES (?,?,?)", C.STREAMS)
    db.executemany("INSERT INTO skills(slug, name, category, description) VALUES (?,?,?,?)", C.SKILLS)
    sid = {r["slug"]: r["id"] for r in db.execute("SELECT id, slug FROM skills")}
    for c in C.CAREERS:
        db.execute("INSERT INTO careers(slug, title, description, interest_tags, degree_backgrounds, certifications, "
                   "portfolio_requirements, interview_prep) VALUES (?,?,?,?,?,?,?,?)", c)
    cid = {r["slug"]: r["id"] for r in db.execute("SELECT id, slug FROM careers")}
    for slug, items in C.CAREER_SKILLS.items():
        db.executemany("INSERT INTO career_skills VALUES (?,?,?)", [(cid[slug], sid[s], lvl) for s, lvl in items])
    for slug, (title, desc, stages) in C.ROADMAPS.items():
        rid = db.execute("INSERT INTO roadmaps(career_id, title, description) VALUES (?,?,?)", (cid[slug], title, desc)).lastrowid
        for i, (t, sk, tgt, hrs, ms, concepts) in enumerate(stages, 1):
            db.execute("INSERT INTO roadmap_stages(roadmap_id, position, title, description, concepts, skill_id, target_level, est_hours, milestone) "
                       "VALUES (?,?,?,?,?,?,?,?,?)", (rid, i, t, "", concepts, sid.get(sk) if sk else None, tgt, hrs, ms))
    return sid, cid


def seed_resources(db, sid):
    for (title, prov, url, skills, cat, topic, rtype, fmt, kind, diff, dur, lang, pricing, desc, tags) in R.R:
        extra = R.PAID_EXTRA.get(title, ("", "", ""))
        note = "Price is set by the provider and not stored here - check the provider for the current INR price." if pricing in ("paid", "freemium") else ""
        rid = db.execute(
            "INSERT INTO resources(title, provider, url, source_url, category, topic, resource_type, format, source_kind, difficulty, "
            "duration_min, language, pricing, price_note, description, tags, strengths, limitations, suitable_for, status, verification_notes) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?, 'unverified', 'Seeded by NAVORA editors; link not yet checked.')",
            (title, prov, url, url, cat, topic, rtype, fmt, kind, diff, dur, lang, pricing, note, desc, tags, *extra)).lastrowid
        for s in skills.split(","):
            db.execute("INSERT OR IGNORE INTO resource_skills VALUES (?,?)", (rid, sid[s]))
    s = R.SPONSORED_DEMO
    db.execute("INSERT INTO sponsored_content(title, sponsor, url, blurb, is_demo, active) VALUES (?,?,?,?,?,?)",
               (s["title"], s["sponsor"], s["url"], s["blurb"], s["is_demo"], s["active"]))


def seed_projects(db, sid):
    for (slug, title, diff, hrs, skills, desc, outcomes, tech, blurb) in P.PROJECTS:
        pid = db.execute("INSERT INTO projects(slug, title, difficulty, est_hours, description, outcomes, technologies, checklist, portfolio_blurb) "
                         "VALUES (?,?,?,?,?,?,?,?,?)", (slug, title, diff, hrs, desc, outcomes, tech, P.CHECKLIST, blurb)).lastrowid
        for s in skills.split(","):
            db.execute("INSERT OR IGNORE INTO project_skills VALUES (?,?)", (pid, sid[s]))
    for (skill, qn, a, b, c, d, ans, expl) in P.QUIZ:
        db.execute("INSERT INTO quiz_questions(skill_id, question, option_a, option_b, option_c, option_d, answer, explanation) "
                   "VALUES (?,?,?,?,?,?,?,?)", (sid[skill], qn, a, b, c, d, ans, expl))


def seed_users(db, sid, cid, admin_password=None):
    pw = admin_password or ""
    generated = False
    if not pw:
        pw, generated = secrets.token_urlsafe(12), True
    from config import Config
    db.execute("INSERT INTO users(email, name, password_hash, role) VALUES (?,?,?, 'admin')",
               (Config.ADMIN_EMAIL, "NAVORA Admin", generate_password_hash(pw)))
    # --- demo student (all of this is labelled Demo Data in the UI)
    uid = db.execute("INSERT INTO users(email, name, password_hash, is_demo) VALUES (?,?,?,1)",
                     (DEMO_EMAIL, "Demo Student", generate_password_hash(DEMO_PASSWORD))).lastrowid
    stream = db.execute("SELECT id FROM streams WHERE slug='btech'").fetchone()["id"]
    db.execute("INSERT INTO profiles(user_id, stream_id, specialization, college, year, semester, career_id, level, minutes_per_day, "
               "language, budget, free_first, onboarded) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1)",
               (uid, stream, "Information Technology", "Demo University", 2, 4, cid["cybersecurity-analyst"], "beginner", 60, "English", "mostly_free", 1))
    db.executemany("INSERT INTO user_interests VALUES (?,?)", [(uid, i) for i in ("Cybersecurity", "Software Development")])
    db.executemany("INSERT INTO user_formats VALUES (?,?)", [(uid, f) for f in ("video", "interactive")])
    levels = {"computer-fundamentals": 60, "python": 45, "sql": 40, "networking": 25, "linux": 20, "git": 30, "security-fundamentals": 10}
    db.executemany("INSERT INTO user_skills VALUES (?,?,?)", [(uid, sid[k], v) for k, v in levels.items()])
    rid = {r["title"]: r["id"] for r in db.execute("SELECT id, title FROM resources")}
    done = ["Crash Course Computer Science", "SQLBolt", "The Python Tutorial (official)"]
    started = ["Cloudflare Learning Center", "Linux Journey"]
    for t in done:
        db.execute("INSERT INTO learning_progress(user_id, resource_id, status, started_at, completed_at) VALUES (?,?, 'completed', datetime('now','-12 day'), datetime('now','-4 day'))", (uid, rid[t]))
    for t in started:
        db.execute("INSERT INTO learning_progress(user_id, resource_id, status) VALUES (?,?, 'started')", (uid, rid[t]))
    today = date.today()
    for i, m in [(0, 40), (1, 55), (2, 30), (3, 60), (5, 45), (6, 50), (8, 35), (9, 70), (11, 25)]:
        db.execute("INSERT INTO study_sessions(user_id, topic, minutes, day, is_demo) VALUES (?,?,?,?,1)",
                   (uid, "Demo session", m, (today - timedelta(days=i)).isoformat()))
    pid = {r["slug"]: r["id"] for r in db.execute("SELECT id, slug FROM projects")}
    db.execute("INSERT INTO user_projects(user_id, project_id, status) VALUES (?,?, 'started')", (uid, pid["password-checker"]))
    for t in ("Cloudflare Learning Center", "OverTheWire: Bandit", "TryHackMe"):
        db.execute("INSERT INTO bookmarks(user_id, kind, ref_id, folder) VALUES (?, 'resource', ?, ?)", (uid, rid[t], "Career"))
    db.execute("INSERT INTO bookmarks(user_id, kind, ref_id, folder) VALUES (?, 'project', ?, 'Projects')", (uid, pid["home-network-lab"]))
    db.execute("INSERT OR IGNORE INTO readiness_items VALUES (?, 'github', 1)", (uid,))
    for msg, kind in (("Demo Data: welcome to the NAVORA demo student account.", "info"),
                      ("Roadmap milestone reached: Computer fundamentals", "milestone")):
        db.execute("INSERT INTO notifications(user_id, kind, message) VALUES (?,?,?)", (uid, kind, msg))
    for name, days, weak, hrs, topics in (("Database Management Systems", 24, 1, 4, "ER model;Normalisation;SQL queries;Transactions;Indexing"),
                                          ("Computer Networks", 31, 0, 3, "OSI model;IP addressing;TCP and UDP;Routing"),
                                          ("Operating Systems", 38, 0, 3, "Processes;Scheduling;Memory management;File systems")):
        sub = db.execute("INSERT INTO semester_subjects(user_id, name, exam_date, is_weak, target_marks, hours_per_week) VALUES (?,?,?,?,?,?)",
                         (uid, name, (today + timedelta(days=days)).isoformat(), weak, 75, hrs)).lastrowid
        for t in topics.split(";"):
            db.execute("INSERT INTO syllabus_topics(subject_id, topic) VALUES (?,?)", (sub, t))
    return pw, generated


def seed_all(db, admin_password=None):
    sid, cid = seed_catalog(db)
    seed_resources(db, sid)
    seed_projects(db, sid)
    out = seed_users(db, sid, cid, admin_password)
    db.commit()
    return out


def main():
    app = create_app()
    with app.app_context():
        db = get_db()
        if "--reset" in sys.argv:
            for (t,) in db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchall():
                db.execute(f"DROP TABLE IF EXISTS {t}")
            db.commit()
        init_db()
        if db.execute("SELECT COUNT(*) FROM users").fetchone()[0]:
            print("Database already has data. Use --reset to wipe and reseed.")
            return
        pw, generated = seed_all(db, app.config["ADMIN_PASSWORD"])
        print(f"Seeded. Admin login: {app.config['ADMIN_EMAIL']}")
        if generated:
            print(f"Generated admin password (shown once, store it safely): {pw}")
        print(f"Demo student: use the 'Try the demo student' button, or {DEMO_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
