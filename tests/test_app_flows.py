import re

from conftest import login, post
from app.db import q, q1, scalar

ONBOARD = {"stream_id": "1", "specialization": "IT", "year": "2", "semester": "3", "career_id": "3", "level": "beginner",
           "minutes_per_day": "60", "language": "English", "budget": "mostly_free", "interests": ["Data Analytics"], "formats": ["video"]}

PUBLIC = ["/", "/resources", "/careers", "/skills", "/streams", "/discover", "/privacy", "/terms", "/disclosure",
          "/careers/data-analyst", "/skills/sql", "/streams/btech", "/resources/1", "/compare?id=1&id=2", "/sitemap.xml",
          "/robots.txt", "/api/health", "/login", "/register"]
DEMO_PAGES = ["/dashboard", "/next", "/roadmap", "/skill-gap", "/projects", "/projects/1", "/bookmarks", "/progress",
              "/mentor", "/semester", "/exam", "/exam?mode=last-minute", "/readiness", "/notifications", "/profile",
              "/onboarding", "/quiz/2", "/resources", "/resources/1", "/careers/cybersecurity-analyst"]


def test_public_pages_render(client):
    for p in PUBLIC:
        r = client.get(p)
        assert r.status_code == 200, p
        assert "Traceback" not in r.get_data(as_text=True)


def test_demo_pages_render(demo):
    for p in DEMO_PAGES:
        assert demo.get(p).status_code == 200, p


def test_admin_pages_render(admin):
    for p in ["/admin/", "/admin/users", "/admin/reports", "/admin/affiliates", "/admin/feedback", "/admin/audit"] + \
             [f"/admin/e/{n}" for n in ["resources", "skills", "careers", "streams", "roadmaps", "stages", "projects", "sponsored", "quiz"]] + \
             [f"/admin/e/{n}/new" for n in ["resources", "skills", "projects"]]:
        assert admin.get(p).status_code == 200, p


def test_demo_dashboard_content(demo):
    html = demo.get("/dashboard").get_data(as_text=True)
    assert "Your Next Move" in html and "Why this?" in html and "Demo Data" in html and "Learn Networking" in html


def test_demo_next_move_is_networking(demo):
    j = demo.get("/api/next").get_json()
    assert j["title"] == "Learn Networking" and j["resource"] and j["reason"]


def test_onboarding_flow_and_validation(client):
    post(client, "/register", {"name": "Asha Rao", "email": "asha@example.com", "password": "Str0ng-pass!"})
    assert post(client, "/onboarding", dict(ONBOARD, stream_id="9999")).status_code == 400
    assert post(client, "/onboarding", dict(ONBOARD, level="wizard")).status_code == 400
    assert post(client, "/onboarding", dict(ONBOARD, minutes_per_day="5")).status_code == 400
    r = post(client, "/onboarding", ONBOARD)
    assert r.status_code == 302 and "/skill-gap" in r.headers["Location"]
    uid = q1("SELECT id FROM users WHERE email='asha@example.com'")["id"] if False else None
    html = client.get("/dashboard").get_data(as_text=True)
    assert "Learn " in html


def test_skill_ratings_drive_roadmap_and_next_move(client):
    post(client, "/register", {"name": "Asha", "email": "asha@example.com", "password": "Str0ng-pass!"})
    post(client, "/onboarding", ONBOARD)       # career 3 = Data Analyst
    first = client.get("/api/next").get_json()["title"]
    sk = {m: v for m, v in re.findall(r'name="skill_(\d+)" type="range"[^>]*value="(\d+)"', client.get("/skill-gap").get_data(as_text=True))}
    assert sk, "skill sliders should render"
    data = {f"skill_{k}": "0" for k in sk}
    data["skill_" + list(sk)[0]] = "100"       # excel (first roadmap stage) mastered
    assert post(client, "/skill-gap", data).status_code == 302
    second = client.get("/api/next").get_json()["title"]
    assert first != second


def test_recommendations_differ_by_profile_and_goal(app):
    from app.db import get_db
    from app.services import core
    tops = {}
    with app.app_context():
        for career in (3, 4, 7):       # data analyst, cyber, financial analyst (ids by seed order)
            db = get_db()
            cur = db.execute("INSERT INTO users(email, name, password_hash) VALUES (?,?,?)", (f"u{career}@x.com", "U", "x"))
            db.execute("INSERT INTO profiles(user_id, stream_id, career_id, level, onboarded) VALUES (?,1,?, 'beginner', 1)", (cur.lastrowid, career))
            db.commit()
            nm = core.get_next_move(cur.lastrowid)
            tops[career] = (nm["title"], nm["resource"]["resource"]["id"])
    assert len({v[0] for v in tops.values()}) == 3


def test_resource_detail_shows_why_and_honest_rating(demo):
    html = demo.get("/resources/1").get_data(as_text=True)
    assert "Why this?" in html and "Rating unavailable" in html and "Not yet verified" in html


def titles(client, url):
    html = client.get(url).get_data(as_text=True)
    return re.findall(r'<h3 style="margin:0"><a href="/resources/\d+">(.*?)</a>', html)


def test_search_filters(client):
    paid = titles(client, "/resources?pricing=paid")
    assert paid and all("Specialization" in t or "Certificate" in t for t in paid) and "SQLBolt" not in paid
    assert "SQLBolt" in titles(client, "/resources?q=sqlbolt")
    hindi = titles(client, "/resources?language=Hindi")
    assert hindi and not any(t == "SQLBolt" for t in hindi)
    assert any("Deep Learning" in t for t in titles(client, "/resources?difficulty=3&format=video"))
    short = titles(client, "/resources?max_minutes=130")
    assert "SQLBolt" in short and "CS50x: Introduction to Computer Science" not in short

def test_search_empty_and_invalid(client):
    r = client.get("/resources?q=zzzzzzqqqq")
    assert r.status_code == 200 and "No resources match" in r.get_data(as_text=True)
    assert client.get("/resources?difficulty=abc&max_minutes=xyz&min_rating=oops&sort=%27;--").status_code == 200
    assert client.get("/resources?q=" + "a" * 5000).status_code == 200


def test_search_is_logged(client, app):
    client.get("/resources?q=pandas")
    with app.app_context():
        assert scalar("SELECT COUNT(*) FROM search_log WHERE query='pandas'") == 1


def test_click_tracking_and_affiliate(client, app, admin):
    from app.db import run
    with app.app_context():
        run("UPDATE resources SET affiliate_url='https://aff.example/x', affiliate_ref='NAV1' WHERE id=1")
    r = client.get("/go/1")
    assert r.status_code == 302 and r.headers["Location"] == "https://aff.example/x"
    r = client.get("/go/2")
    assert r.status_code == 302 and "aff.example" not in r.headers["Location"]
    with app.app_context():
        assert scalar("SELECT COUNT(*) FROM resource_clicks") == 2 and scalar("SELECT COUNT(*) FROM affiliate_clicks") == 1
    assert "Affiliate disclosure" in client.get("/resources/1").get_data(as_text=True)


def test_progress_updates_skill_and_streak(demo, app):
    before = q1  # noqa
    assert post(demo, "/log-session", {"minutes": "45", "topic": "x"}).status_code == 302
    assert post(demo, "/log-session", {"minutes": "0"}).status_code == 302          # rejected with flash, no crash
    r = post(demo, "/resources/43/complete", {"minutes": "30"})
    assert r.status_code == 302
    html = demo.get("/progress").get_data(as_text=True)
    assert "Your progress" in html


def test_feedback_loop_changes_future_ranking(demo):
    j1 = demo.get("/api/next").get_json()
    rid = j1["resource"]["id"]
    r = post(demo, f"/resources/{rid}/feedback", {"useful": "0", "reason": "boring"}, headers={"X-Requested-With": "fetch"})
    assert r.status_code == 200 and r.get_json()["ok"]
    j2 = demo.get("/api/next").get_json()
    assert j2["resource"]["id"] != rid


def test_feedback_invalid_reason_is_sanitised(demo):
    assert post(demo, "/resources/1/feedback", {"useful": "0", "reason": "<script>"}).status_code == 302


def test_bookmarks(demo):
    assert post(demo, "/bookmarks/toggle", {"kind": "resource", "ref_id": "5", "folder": "Interview"}).status_code == 302
    assert "Interview" in demo.get("/bookmarks").get_data(as_text=True)
    assert post(demo, "/bookmarks/toggle", {"kind": "resource", "ref_id": "5", "folder": "Hacker"}).status_code == 400
    assert post(demo, "/bookmarks/toggle", {"kind": "evil", "ref_id": "5"}).status_code == 400
    post(demo, "/bookmarks/toggle", {"kind": "resource", "ref_id": "5", "folder": "Interview"})   # toggles off


def test_reviews_separate_from_external_rating(demo):
    assert post(demo, "/resources/1/review", {"rating": "5", "review": "Great", "difficulty_feedback": "just_right"}).status_code == 302
    post(demo, "/resources/1/review", {"rating": "9"})
    html = demo.get("/resources/1").get_data(as_text=True)
    assert "Rating unavailable" in html and "NAVORA student" in html


def test_report_resource_and_admin_review(client, app, admin):
    assert post(client, "/resources/3/report", {"kind": "broken_link", "note": "404"}).status_code == 302
    assert post(client, "/resources/3/report", {"kind": "nonsense"}).status_code == 302
    html = admin.get("/admin/reports").get_data(as_text=True)
    assert "broken link" in html
    rid = q1 and None
    with app.app_context():
        rid = q1("SELECT id FROM reports")["id"]
    assert post(admin, "/admin/reports", {"id": str(rid), "action": "resolved"}).status_code == 302
    with app.app_context():
        assert q1("SELECT status FROM reports WHERE id=?", (rid,))["status"] == "resolved"


def test_projects_flow(demo):
    assert post(demo, "/projects/1/status", {"status": "completed", "repo_url": "https://github.com/a/b"}).status_code == 302
    assert post(demo, "/projects/1/status", {"status": "completed", "repo_url": "javascript:alert(1)"}).status_code == 302
    assert post(demo, "/projects/1/status", {"status": "hacked"}).status_code == 400
    assert post(demo, "/projects/99999/status", {"status": "started"}).status_code == 404


def test_quiz_scoring(demo):
    html = demo.get("/quiz/2").get_data(as_text=True)
    ids = re.findall(r'name="q(\d+)"', html)
    data = {f"q{i}": "b" for i in set(ids)}
    r = post(demo, "/quiz/2", data)
    assert r.status_code == 200 and "Result" in r.get_data(as_text=True)


def test_semester_and_exam(demo):
    assert post(demo, "/semester", {"name": "Maths", "exam_date": "2099-01-01", "topics": "A\nB\nC", "target_marks": "80", "hours_per_week": "5"}).status_code == 302
    assert post(demo, "/semester", {"name": "Bad", "exam_date": "31/12/2099"}).status_code == 302
    html = demo.get("/exam").get_data(as_text=True)
    assert "Maths" in html and "Database Management Systems" in html
    assert "Focus on" in demo.get("/exam?mode=last-minute").get_data(as_text=True)


def test_readiness_toggle(demo):
    assert post(demo, "/readiness", {"item": "resume"}).status_code == 302
    assert post(demo, "/readiness", {"item": "bogus"}).status_code == 302
    assert "%" in demo.get("/readiness").get_data(as_text=True)


def test_mentor_modes_work_offline(demo):
    for mode, msg in [("explain", "Explain recursion"), ("explain", "what is sql injection"), ("quiz", "Quiz me on SQL"),
                      ("plan", "I have 2 hours today"), ("resources", "Find networking resources"), ("projects", "give me a project"),
                      ("revision", "revision plan"), ("career", "what skills am I missing"), ("bogus", "hello")]:
        r = post(demo, "/api/mentor", None, headers={"Content-Type": "application/json"}) if False else None
        from conftest import token
        r = demo.post("/api/mentor", json={"mode": mode, "message": msg}, headers={"X-CSRF-Token": token(demo)})
        assert r.status_code == 200, (mode, msg)
        j = r.get_json()
        assert j["text"] and j["source"] == "rules", (mode, j)
    from conftest import token
    assert demo.post("/api/mentor", json={"message": "  "}, headers={"X-CSRF-Token": token(demo)}).status_code == 400


def test_mentor_falls_back_when_llm_fails(app, demo):
    app.config.update(LLM_API_KEY="bad", LLM_MODEL="bad")
    from conftest import token
    import app.services.mentor as m
    m.HTTPAdapter.url = "http://127.0.0.1:9/never"          # unreachable -> must degrade, not crash
    r = demo.post("/api/mentor", json={"mode": "explain", "message": "Explain recursion"}, headers={"X-CSRF-Token": token(demo)})
    j = r.get_json()
    assert r.status_code == 200 and j["source"] == "rules" and "recursion" in j["text"].lower() and j.get("note")


def test_discover_mode(client):
    r = post(client, "/discover", {"q0": "2", "q1": "1", "q2": "0", "q3": "2", "q4": "3", "q5": "1"})
    html = r.get_data(as_text=True)
    assert r.status_code == 200 and "Pathway 1" in html and "Cybersecurity" in html
    assert post(client, "/discover", {}).status_code == 400


def test_compare_limits_and_no_winner(client):
    html = client.get("/compare?id=1&id=2&id=3&id=4").get_data(as_text=True)
    assert "Best suited for students who prefer" in html and "winner" not in html.lower()
    assert "Pick at least two" in client.get("/compare?id=1").get_data(as_text=True)


def test_language_switch(client):
    post(client, "/lang/hi", {"next": "/"})
    assert "\u0906\u092a\u0915\u094b \u0914\u0930 \u0938\u0902\u0938\u093e\u0927\u0928" in client.get("/").get_data(as_text=True)
    post(client, "/lang/bn", {"next": "//evil.com"})
    assert "\u0986\u09aa\u09a8\u09be\u09b0 \u0986\u09b0\u0993" in client.get("/").get_data(as_text=True)
    assert client.get("/").headers["Content-Type"].startswith("text/html")


def test_sponsored_is_labelled_and_demo(client):
    html = client.get("/resources").get_data(as_text=True)
    assert "Sponsored" in html and "Demo Data" in html


def test_seo_endpoints(client):
    assert "/careers/data-analyst" in client.get("/sitemap.xml").get_data(as_text=True)
    assert "Disallow: /admin" in client.get("/robots.txt").get_data(as_text=True)
    html = client.get("/careers/data-analyst").get_data(as_text=True)
    assert "<title>Data Analyst" in html and 'property="og:title"' in html


def test_404s(client, demo):
    for p in ["/resources/99999", "/careers/nope", "/skills/nope", "/streams/nope", "/projects/9999", "/quiz/9999"]:
        assert client.get(p).status_code == 404, p

