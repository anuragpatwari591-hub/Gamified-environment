from conftest import login, post
from app.db import q1, scalar

RES = {"title": "Test Course", "provider": "Prov", "url": "https://example.com/c", "source_url": "https://example.com/c",
       "resource_type": "course", "format": "video", "source_kind": "official", "difficulty": "1", "pricing": "free",
       "status": "unverified", "language": "English", "category": "Technology", "skill_ids": ["1", "2"]}


def test_admin_create_edit_delete_resource(admin, app):
    r = post(admin, "/admin/e/resources/new", RES)
    assert r.status_code == 302
    with app.app_context():
        row = q1("SELECT * FROM resources WHERE title='Test Course'")
        assert row and scalar("SELECT COUNT(*) FROM resource_skills WHERE resource_id=?", (row["id"],)) == 2
        rid = row["id"]
    assert post(admin, f"/admin/e/resources/{rid}", dict(RES, title="Renamed")).status_code == 302
    assert "Renamed" in admin.get("/admin/e/resources").get_data(as_text=True)
    assert post(admin, f"/admin/e/resources/{rid}/delete").status_code == 302
    with app.app_context():
        assert q1("SELECT 1 FROM resources WHERE id=?", (rid,)) is None
        assert scalar("SELECT COUNT(*) FROM audit_logs") >= 3


def test_admin_validation_rejects_bad_input(admin):
    assert post(admin, "/admin/e/resources/new", dict(RES, url="javascript:alert(1)")).status_code == 400
    assert post(admin, "/admin/e/resources/new", dict(RES, title="")).status_code == 400
    assert post(admin, "/admin/e/resources/new", dict(RES, pricing="gratis")).status_code == 400
    assert post(admin, "/admin/e/resources/new", dict(RES, duration_min="abc")).status_code == 400
    assert post(admin, "/admin/e/resources/new", dict(RES, rating="9")).status_code == 400      # CHECK constraint -> graceful


def test_admin_duplicate_slug_handled(admin):
    d = {"name": "Dup", "slug": "python", "category": "x", "description": ""}
    assert post(admin, "/admin/e/skills/new", d).status_code == 400


def test_admin_unknown_entity_404(admin):
    assert admin.get("/admin/e/users").status_code == 404
    assert admin.get("/admin/e/resources/99999").status_code == 404


def test_admin_verify_sets_date(admin, app):
    assert post(admin, "/admin/resources/1/verify", {"status": "active", "notes": "ok"}).status_code == 302
    with app.app_context():
        r = q1("SELECT status, last_verified_at, verification_notes FROM resources WHERE id=1")
    assert r["status"] == "active" and r["last_verified_at"] and r["verification_notes"] == "ok"
    assert post(admin, "/admin/resources/1/verify", {"status": "bogus"}).status_code == 400


def test_broken_resources_hidden_from_search(admin, client):
    post(admin, "/admin/resources/4/verify", {"status": "hidden"})
    assert "/resources/4\"" not in client.get("/resources").get_data(as_text=True)
    assert client.get("/resources/4").status_code == 404


def test_admin_cannot_deactivate_self_but_can_others(admin, app):
    with app.app_context():
        me = q1("SELECT id FROM users WHERE role='admin'")["id"]
        demo = q1("SELECT id FROM users WHERE is_demo=1")["id"]
    post(admin, f"/admin/users/{me}/toggle")
    post(admin, f"/admin/users/{demo}/toggle")
    with app.app_context():
        assert q1("SELECT is_active FROM users WHERE id=?", (me,))["is_active"] == 1
        assert q1("SELECT is_active FROM users WHERE id=?", (demo,))["is_active"] == 0


def test_admin_user_search(admin):
    assert "Demo Student" in admin.get("/admin/users?q=demo").get_data(as_text=True)
    assert "No users found" in admin.get("/admin/users?q=zzzzz").get_data(as_text=True)


def test_affiliate_conversion_is_manual_and_analytics_real(admin, client, app):
    post(admin, "/admin/e/resources/1", dict(RES, title="Crash Course", affiliate_url="https://aff.example/1", affiliate_ref="X1"))
    client.get("/go/1")
    html = admin.get("/admin/").get_data(as_text=True)
    assert "Affiliate clicks" in html
    with app.app_context():
        cid = q1("SELECT id FROM affiliate_clicks")["id"]
        assert scalar("SELECT COUNT(*) FROM affiliate_clicks WHERE converted=1") == 0
    post(admin, "/admin/affiliates", {"id": str(cid), "action": "convert", "commission": "120.5"})
    with app.app_context():
        assert scalar("SELECT SUM(commission_inr) FROM affiliate_clicks WHERE converted=1") == 120.5


def test_admin_manages_sponsored_and_roadmap_stage(admin, app):
    s = {"title": "Sp", "sponsor": "ACME", "url": "https://acme.example", "blurb": "b", "is_demo": "1", "active": "1"}
    assert post(admin, "/admin/e/sponsored/new", s).status_code == 302
    st = {"roadmap_id": "1", "position": "50", "title": "Extra stage", "target_level": "50", "est_hours": "5"}
    assert post(admin, "/admin/e/stages/new", st).status_code == 302
    assert post(admin, "/admin/e/stages/new", st).status_code == 400            # duplicate (roadmap, position)
    with app.app_context():
        assert q1("SELECT 1 FROM roadmap_stages WHERE title='Extra stage'")


def test_csrf_enforced_on_admin_posts(admin):
    assert admin.post("/admin/e/skills/1/delete").status_code == 400


def test_delete_referenced_skill_is_handled(admin):
    r = post(admin, "/admin/e/skills/2/delete")        # python is referenced by career_skills etc. (cascade or block, but no crash)
    assert r.status_code == 302
