"""Explainable recommendation engine.

Pure functions over plain dicts so the algorithm can be unit-tested and explained without a database.

    match_score = 100 * sum(w_i * c_i) / sum(w_i)      c_i in [0, 1]

Every component c_i also produces a human-readable reason, so each recommendation carries its own explanation.
Weights live in weights.json (configurable, not hard-coded). Sponsored status is deliberately NOT an input.
"""
import json
from datetime import date, datetime
from pathlib import Path

WEIGHTS_PATH = Path(__file__).with_name("weights.json")
LEVEL_NAMES = {1: "beginner", 2: "intermediate", 3: "advanced"}
FORMAT_LABEL = {"video": "video lessons", "reading": "reading", "interactive": "interactive lessons",
                "practice": "practice-first", "project": "project-based learning"}


def load_weights(path=WEIGHTS_PATH):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


WEIGHTS = load_weights()


# ---------------------------------------------------------------- helpers
def _days_since(iso):
    if not iso:
        return None
    try:
        d = datetime.fromisoformat(str(iso)[:19].replace("T", " ")).date()
    except ValueError:
        return None
    return (date.today() - d).days


def freshness(res):
    days = _days_since(res.get("last_verified_at"))
    if days is None:
        return 0.3                      # never verified
    if days <= 90:
        return 1.0
    if days >= 365:
        return 0.4
    return 1.0 - 0.6 * (days - 90) / 275


def level_to_difficulty(level):
    return 1 if level < 35 else 2 if level < 70 else 3


def quality(res, w=None, community=None):
    """Generic (non-personalised) quality score 0-100 with a breakdown.

    Missing signals are dropped and the remaining weights renormalised - a missing rating is never invented.
    community = (avg_rating, n) from NAVORA users only, kept separate from the external rating.
    """
    w = w or WEIGHTS
    qw = w["quality_weights"]
    parts, used = {}, {}
    if res.get("rating") is not None:
        n = res.get("rating_count") or 0
        conf = 1.0 if n >= 1000 else 0.85 if n >= 100 else 0.7 if n > 0 else 0.8   # unknown count -> mild shrink
        parts["rating"] = (res["rating"] / 5.0) * conf
    parts["credibility"] = w["source_credibility"].get(res.get("source_kind", "community"), 0.6)
    parts["freshness"] = freshness(res)
    if community and community[1] >= 3:
        parts["community"] = community[0] / 5.0
    for k, v in parts.items():
        used[k] = qw[k]
    total_w = sum(used.values())
    score = 100 * sum(parts[k] * used[k] for k in parts) / total_w
    return {"score": round(score), "parts": parts, "rating_available": "rating" in parts,
            "community_available": "community" in parts}


# ---------------------------------------------------------------- context
def make_context(**kw):
    """Normalised user context. Keys documented here so callers and tests agree."""
    ctx = {
        "career_id": None, "career_skills": {},          # skill_id -> required level
        "interests": [], "formats": set(), "level": 1,   # 1..3
        "minutes_per_day": 60, "language": "English", "budget": "mostly_free", "free_first": True,
        "skill_levels": {},                              # skill_id -> 0..100
        "focus_skill_ids": set(),                        # current roadmap stage skill(s)
        "roadmap_order": [],                             # [(skill_id, target_level)] in stage order
        "completed": set(), "feedback": [],              # feedback rows: dict(resource, useful, reason)
        "resources_by_id": {},
    }
    ctx.update(kw)
    return ctx


def _unmet_prereq_skills(ctx, skill_ids):
    """Roadmap skills that come BEFORE the earliest stage touched by these skills and are not yet at target."""
    order = ctx["roadmap_order"]
    idx = [i for i, (sid, _) in enumerate(order) if sid in skill_ids]
    if not idx:
        return None
    first = min(idx)
    return [sid for sid, tgt in order[:first] if ctx["skill_levels"].get(sid, 0) < tgt]


# ---------------------------------------------------------------- scoring
def score_resource(res, ctx, weights=None):
    """Return dict(score, parts, reasons, caveats) for one resource. res['skill_ids'] must be a set."""
    w = weights or WEIGHTS
    sk = set(res.get("skill_ids", []))
    c, reasons, caveats = {}, [], []
    cs = ctx["career_skills"]

    # career relevance: how much of the resource addresses a skill still missing for the target career
    if ctx["career_id"]:
        hits = [s for s in sk if s in cs]
        if hits:
            gaps = [max(0, cs[s] - ctx["skill_levels"].get(s, 0)) for s in hits]
            c["career_relevance"] = 0.6 + 0.4 * min(1.0, max(gaps) / 60) if max(gaps) > 0 else 0.3
            if max(gaps) > 0:
                reasons.append(f"It builds a skill your target career ({ctx.get('career_title', 'goal')}) needs "
                               f"and you are still short on.")
        else:
            c["career_relevance"] = 0.0
    else:
        c["career_relevance"] = 0.5

    # skill relevance: is it the skill of your current roadmap stage?
    focus = ctx["focus_skill_ids"]
    if sk & focus:
        c["skill_relevance"] = 1.0
        reasons.append("It covers the stage you are on right now in your roadmap.")
    elif sk & {s for s, _ in ctx["roadmap_order"]}:
        c["skill_relevance"] = 0.35
    else:
        c["skill_relevance"] = 0.0 if ctx["roadmap_order"] else 0.4

    # prerequisites
    unmet = _unmet_prereq_skills(ctx, sk) if sk else None
    if unmet is None:
        c["prerequisite_fit"] = 0.7
    elif unmet and not (sk & focus):
        c["prerequisite_fit"] = 0.25
        caveats.append("Earlier roadmap stages are not finished yet, so this may be premature.")
    else:
        c["prerequisite_fit"] = 1.0
        if sk & focus:
            reasons.append("Its prerequisites on your roadmap are already covered.")

    # learning style
    if ctx["formats"]:
        if res["format"] in ctx["formats"]:
            c["learning_style"] = 1.0
            reasons.append(f"It matches your preference for {FORMAT_LABEL.get(res['format'], res['format'])}.")
        else:
            c["learning_style"] = 0.4
    else:
        c["learning_style"] = 0.6

    # difficulty
    if sk:
        lv = sum(ctx["skill_levels"].get(s, 0) for s in sk) / len(sk)
    else:
        lv = {1: 15, 2: 50, 3: 85}[ctx["level"]]
    target = level_to_difficulty(lv)
    c["difficulty_fit"] = max(0.0, 1 - abs(res["difficulty"] - target) / 2)
    if res["difficulty"] == target:
        reasons.append(f"Its {LEVEL_NAMES[res['difficulty']]} difficulty fits your current level in this topic.")
    elif res["difficulty"] > target:
        caveats.append("This may be harder than your current level.")

    # language
    lang = ctx["language"]
    if res["language"].lower() == lang.lower():
        c["language"] = 1.0
        if lang.lower() != "english":
            reasons.append(f"It is available in {lang}, your preferred language.")
    else:
        c["language"] = 0.3 if lang.lower() != "english" else 0.5
        if lang.lower() != "english":
            caveats.append(f"Not in your preferred language ({lang}).")

    # time
    d = res.get("duration_min")
    if d is None:
        c["time_fit"] = 0.5
        caveats.append("Duration not listed.")
    else:
        ratio = d / max(1, ctx["minutes_per_day"] * 7)
        c["time_fit"] = 1.0 if ratio <= 1 else ratio ** -0.5
        if ratio <= 1:
            reasons.append("You can finish it within about a week at your study pace.")
        elif ratio > 3:
            caveats.append("This is a long commitment at your current study time; plan to study it in chunks.")

    # quality (generic)
    qual = quality(res, w, res.get("community"))
    c["quality"] = qual["score"] / 100
    if not qual["rating_available"]:
        caveats.append("Rating unavailable.")
    if res.get("source_kind") in ("official", "university", "government"):
        reasons.append(f"It comes from a {res['source_kind']} source ({res['provider']}).")
    c["freshness"] = freshness(res)
    if res.get("last_verified_at") is None:
        caveats.append("Link not yet verified by NAVORA.")

    # budget
    b = ctx["budget"]
    if res["pricing"] == "free":
        c["budget_fit"] = 1.0
    elif res["pricing"] == "freemium":
        c["budget_fit"] = 0.7 if b != "free" else 0.4
    else:
        c["budget_fit"] = {"free": 0.0, "mostly_free": 0.35, "paid_ok": 0.8, "premium": 1.0}[b]
        caveats.append("Paid resource.")
    if res["pricing"] == "free":
        reasons.append("It is free.")

    # interests
    hay = " ".join([res.get("title", ""), res.get("topic", ""), res.get("tags", ""), res.get("category", "")]).lower()
    ints = [i for i in ctx["interests"] if i.lower().split()[0] in hay]
    c["interest_match"] = min(1.0, len(ints) / 2) if ctx["interests"] else 0.5
    if ints:
        reasons.append(f"It relates to your interest in {ints[0]}.")

    # free-first bonus
    active = {k: w[k] for k in c if k in w}
    if ctx["free_first"]:
        c["free_first_bonus"] = {"free": 1.0, "freemium": 0.5, "paid": 0.0}[res["pricing"]]
        active["free_first_bonus"] = w["free_first_bonus"]
    total_w = sum(active.values())
    base = sum(active[k] * c[k] for k in active) / total_w

    # feedback loop: multiplicative penalties from previous "not useful" signals
    factor, fb_notes = 1.0, []
    for fb in ctx["feedback"]:
        other = ctx["resources_by_id"].get(fb["resource_id"])
        if other is None:
            continue
        if fb["resource_id"] == res["id"]:
            if not fb["useful"]:
                factor *= 0.1
                fb_notes.append("You marked this as not useful before.")
            continue
        sim = 0.0
        osk = set(other.get("skill_ids", []))
        if fb["useful"]:
            if other["format"] == res["format"] and osk & sk:
                factor *= 1.05
            continue
        r = fb["reason"]
        if r == "too_difficult" and res["difficulty"] >= other["difficulty"] and osk & sk:
            sim = 1.0
        elif r == "too_long" and (res.get("duration_min") or 0) >= (other.get("duration_min") or 10 ** 9):
            sim = 0.6
        elif r in ("boring", "wrong_style") and res["format"] == other["format"]:
            sim = 0.8
        elif r in ("wrong_topic", "not_relevant") and osk & sk:
            sim = 1.0
        if sim:
            factor *= 1 - w["feedback_penalty"] * sim
            fb_notes.append("Adjusted down because of your earlier feedback.")
    score = max(0.0, min(100.0, 100 * base * min(factor, 1.1)))
    caveats += list(dict.fromkeys(fb_notes))
    return {"score": round(score), "parts": c, "reasons": reasons, "caveats": caveats,
            "quality": qual, "feedback_factor": round(factor, 3)}


def explain(res, scored, ctx):
    """Compose the 'Why this resource?' text from the reasons the scorer produced."""
    if ctx.get("career_title"):
        head = f"Your goal is {ctx['career_title']} and you are at {LEVEL_NAMES[ctx['level']]} level."
    else:
        head = f"You are at {LEVEL_NAMES[ctx['level']]} level."
    body = scored["reasons"][:4] or ["It is a reasonable general match for your profile."]
    return {"headline": head, "reasons": body, "caveats": scored["caveats"][:3]}


def rank(resources, ctx, limit=5, exclude_completed=True, min_free_alternative=True):
    """Rank resources for a user. Paid items are only kept when they add something over free options
    (a free alternative is attached, or none exists for the skill)."""
    ctx = dict(ctx)
    ctx["resources_by_id"] = {r["id"]: r for r in resources}
    out = []
    for r in resources:
        if r["status"] in ("hidden", "broken"):
            continue
        if exclude_completed and r["id"] in ctx["completed"]:
            continue
        s = score_resource(r, ctx)
        out.append({"resource": r, "score": s["score"], "scored": s, "why": explain(r, s, ctx)})
    out.sort(key=lambda x: (-x["score"], x["resource"]["title"]))
    if min_free_alternative:
        for item in out:
            r = item["resource"]
            if r["pricing"] == "paid":
                alts = [o["resource"] for o in out if o["resource"]["pricing"] == "free"
                        and set(o["resource"]["skill_ids"]) & set(r["skill_ids"]) and o["resource"]["id"] != r["id"]]
                item["free_alternatives"] = alts[:2]
    return out[:limit]


# ---------------------------------------------------------------- next move
def next_move(ctx, stages, resources, projects_by_skill=None):
    """stages: ordered list of dicts(id,title,skill_id,target_level,est_hours,milestone,done).
    Returns the single best next action with reason, time, resource, expected outcome and follow-up."""
    projects_by_skill = projects_by_skill or {}
    current = next((s for s in stages if not s["done"]), None)
    if current is None:
        return {"kind": "portfolio", "title": "Turn your skills into proof",
                "reason": "You have finished every stage of your roadmap. The best next step is to publish your work.",
                "minutes": ctx["minutes_per_day"], "resource": None, "outcome": "A portfolio ready to show recruiters.",
                "after": "Complete the Career Readiness checklist.", "stage": None}
    ctx = dict(ctx)
    ctx["focus_skill_ids"] = {current["skill_id"]} if current["skill_id"] else set()
    pool = [r for r in resources if current["skill_id"] in r["skill_ids"]] or resources
    ranked = rank(pool, ctx, limit=3)
    top = ranked[0] if ranked else None
    lvl = ctx["skill_levels"].get(current["skill_id"], 0)
    why = [f"It is the next unfinished stage of your roadmap (\"{current['title']}\")."]
    if lvl:
        why.append(f"You are at about {lvl}% in this skill and the stage target is {current['target_level']}%.")
    else:
        why.append("You have not started this skill yet.")
    if top:
        why += top["why"]["reasons"][:2]
    minutes = ctx["minutes_per_day"]
    if top and top["resource"].get("duration_min"):
        minutes = min(top["resource"]["duration_min"], max(20, ctx["minutes_per_day"]))
    proj = projects_by_skill.get(current["skill_id"])
    after = (f"Build the project \"{proj['title']}\"." if proj else
             f"Finish the stage milestone: {current['milestone']}" if current["milestone"] else "Move to the next stage.")
    return {"kind": "learn", "title": f"Learn {current['title']}", "reason": " ".join(why), "reasons": why,
            "minutes": minutes, "resource": top, "alternatives": ranked[1:], "outcome": current["milestone"],
            "after": after, "stage": current, "project": proj}
