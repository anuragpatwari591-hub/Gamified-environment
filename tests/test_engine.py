"""Unit tests for the explainable recommendation engine (pure functions, no DB)."""
from datetime import date, timedelta

from app.recommendation import engine


def res(i, **kw):
    base = dict(id=i, title=f"R{i}", provider="P", format="video", source_kind="community", difficulty=1, duration_min=120,
                language="English", pricing="free", description="", tags="", category="Technology", topic="",
                rating=None, rating_count=None, last_verified_at=None, status="active", skill_ids={1}, community=None)
    base.update(kw)
    return base


def ctx(**kw):
    base = dict(career_id=1, career_title="Data Analyst", career_skills={1: 60}, level=1, skill_levels={1: 10},
                focus_skill_ids={1}, roadmap_order=[(1, 60)])
    base.update(kw)
    return engine.make_context(**base)


def test_missing_rating_is_never_invented():
    q = engine.quality(res(1))
    assert q["rating_available"] is False and "rating" not in q["parts"]


def test_rating_raises_quality():
    assert engine.quality(res(1, rating=4.8, rating_count=5000))["score"] > engine.quality(res(1))["score"]


def test_official_source_more_credible_than_community():
    assert engine.quality(res(1, source_kind="official"))["score"] > engine.quality(res(1, source_kind="community"))["score"]


def test_freshness_decays():
    fresh = (date.today() - timedelta(days=10)).isoformat()
    old = (date.today() - timedelta(days=400)).isoformat()
    assert engine.freshness(res(1, last_verified_at=fresh)) == 1.0
    assert engine.freshness(res(1, last_verified_at=old)) < 0.5
    assert engine.freshness(res(1)) < 0.5


def test_learning_style_changes_ranking():
    pool = [res(1, format="video"), res(2, format="reading")]
    v = engine.rank(pool, ctx(formats={"video"}), limit=2)
    r = engine.rank(pool, ctx(formats={"reading"}), limit=2)
    assert v[0]["resource"]["id"] == 1 and r[0]["resource"]["id"] == 2


def test_difficulty_fit_for_levels():
    pool = [res(1, difficulty=1), res(2, difficulty=3)]
    assert engine.rank(pool, ctx(skill_levels={1: 5}), limit=2)[0]["resource"]["id"] == 1
    assert engine.rank(pool, ctx(skill_levels={1: 90}), limit=2)[0]["resource"]["id"] == 2


def test_language_preference():
    pool = [res(1, language="English"), res(2, language="Hindi")]
    assert engine.rank(pool, ctx(language="Hindi"), limit=2)[0]["resource"]["id"] == 2


def test_free_first_prefers_free():
    pool = [res(1, pricing="paid"), res(2, pricing="free")]
    assert engine.rank(pool, ctx(free_first=True, budget="free"), limit=2, min_free_alternative=False)[0]["resource"]["id"] == 2


def test_budget_premium_without_free_first_allows_paid_to_compete():
    pool = [res(1, pricing="paid", source_kind="official"), res(2, pricing="free", source_kind="community")]
    top = engine.rank(pool, ctx(free_first=False, budget="premium"), limit=2, min_free_alternative=False)[0]
    assert top["resource"]["id"] == 1


def test_sponsored_flag_does_not_affect_score():
    a = engine.score_resource(res(1), ctx())
    b = engine.score_resource(res(1, is_sponsored=1, affiliate_url="https://x.example/", commission_pct=40), ctx())
    assert a["score"] == b["score"]


def test_every_recommendation_has_reasons():
    for item in engine.rank([res(1), res(2, format="reading")], ctx(formats={"video"}), limit=2):
        assert item["why"]["reasons"] and item["why"]["headline"]


def test_unrated_resource_carries_caveat():
    s = engine.score_resource(res(1), ctx())
    assert "Rating unavailable." in s["caveats"]


def test_prerequisite_penalises_premature_resources():
    c = ctx(roadmap_order=[(2, 60), (1, 60)], skill_levels={1: 10, 2: 0}, focus_skill_ids={2})
    early = engine.score_resource(res(1, skill_ids={1}), c)
    assert early["parts"]["prerequisite_fit"] < 0.5 and any("Earlier" in x for x in early["caveats"])


def test_feedback_not_useful_excludes_that_resource():
    pool = [res(1), res(2)]
    c = ctx(feedback=[{"resource_id": 1, "useful": 0, "reason": "boring"}])
    assert engine.rank(pool, c, limit=2)[0]["resource"]["id"] == 2


def test_feedback_wrong_style_demotes_same_format():
    pool = [res(1, format="video"), res(2, format="video"), res(3, format="reading")]
    base = engine.rank(pool, ctx(formats=set()), limit=3, min_free_alternative=False)
    c = ctx(formats=set(), feedback=[{"resource_id": 1, "useful": 0, "reason": "wrong_style"}])
    after = {i["resource"]["id"]: i["score"] for i in engine.rank(pool, c, limit=3, min_free_alternative=False)}
    before = {i["resource"]["id"]: i["score"] for i in base}
    assert after[2] < before[2] and after[3] == before[3]


def test_feedback_too_long_demotes_longer():
    pool = [res(1, duration_min=60), res(2, duration_min=600), res(3, duration_min=30)]
    c = ctx(feedback=[{"resource_id": 1, "useful": 0, "reason": "too_long"}])
    after = {i["resource"]["id"]: i["score"] for i in engine.rank(pool, c, limit=3, min_free_alternative=False)}
    base = {i["resource"]["id"]: i["score"] for i in engine.rank(pool, ctx(), limit=3, min_free_alternative=False)}
    assert after[2] < base[2] and after[3] == base[3]


def test_paid_gets_free_alternative():
    pool = [res(1, pricing="paid"), res(2, pricing="free")]
    items = engine.rank(pool, ctx(budget="premium", free_first=False), limit=2)
    paid = next(i for i in items if i["resource"]["id"] == 1)
    assert paid["free_alternatives"][0]["id"] == 2


def test_completed_resources_excluded():
    assert [i["resource"]["id"] for i in engine.rank([res(1), res(2)], ctx(completed={1}), limit=5)] == [2]


def test_next_move_picks_first_incomplete_stage():
    stages = [dict(id=1, title="A", skill_id=1, target_level=60, est_hours=5, milestone="m1", done=True),
              dict(id=2, title="B", skill_id=2, target_level=60, est_hours=5, milestone="m2", done=False)]
    pool = [res(1, skill_ids={1}), res(2, skill_ids={2})]
    c = ctx(career_skills={1: 60, 2: 60}, skill_levels={1: 70, 2: 0}, roadmap_order=[(1, 60), (2, 60)])
    nm = engine.next_move(c, stages, pool)
    assert nm["title"] == "Learn B" and nm["resource"]["resource"]["id"] == 2 and nm["reason"]


def test_next_move_when_roadmap_finished():
    nm = engine.next_move(ctx(), [dict(id=1, title="A", skill_id=1, target_level=60, est_hours=5, milestone="", done=True)], [res(1)])
    assert nm["kind"] == "portfolio"


def test_weights_are_configurable_not_hardcoded():
    w = dict(engine.WEIGHTS)
    pool = res(1, format="video")
    c = ctx(formats={"reading"})
    low = engine.score_resource(pool, c, dict(w, learning_style=0))["score"]
    high = engine.score_resource(pool, c, dict(w, learning_style=60))["score"]
    assert low != high
