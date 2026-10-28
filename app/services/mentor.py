"""AI Study Mentor.

Architecture: Mentor -> LLMAdapter (optional) -> deterministic fallback.
The platform NEVER depends on the external service: any adapter failure falls back to rule-based answers
built from the user's own profile, roadmap and the resource database.
"""
import json
import random
import urllib.request

from flask import current_app

from ..db import q, q1
from . import core

MODES = {"explain": "Explain", "quiz": "Quiz Me", "plan": "Plan My Day", "resources": "Find Resources",
         "projects": "Project Ideas", "revision": "Revision", "career": "Career Guidance"}

# Small hand-written knowledge base used by the deterministic Explain mode (concise, original wording).
KB = {
    "recursion": "Recursion is when a function solves a problem by calling itself on a smaller version of the same "
                 "problem, until it reaches a base case that it can answer directly. Example: factorial(n) = n * "
                 "factorial(n-1), with factorial(0) = 1 as the base case. Two things to check every time: a base case "
                 "exists, and each call moves closer to it.",
    "sql join": "A JOIN combines rows from two tables using a related column. INNER JOIN keeps only matching rows; "
                "LEFT JOIN keeps every row from the left table and fills NULLs where nothing matches. Think: 'start "
                "from the left table, attach matching info from the right'.",
    "git": "Git records snapshots of your project so you can go back, compare, and collaborate. Core loop: edit files, "
           "`git add` to stage, `git commit` to save a snapshot, `git push` to share. Branches let you try ideas without "
           "touching the main line of work.",
    "variable": "A variable is a named box in memory that holds a value. You can read it, change it, and use it in "
                "calculations. In Python: `age = 20` creates the variable `age`.",
    "api": "An API is a defined way for programs to talk to each other. A web API usually receives an HTTP request "
           "(like GET /users/5) and returns data, often as JSON.",
    "tcp": "TCP is a reliable transport protocol: it sets up a connection (three-way handshake), numbers data, "
           "retransmits lost packets and delivers bytes in order. UDP skips these guarantees for speed.",
    "http": "HTTP is the request/response protocol of the web. A client sends a method (GET, POST...), a path and "
            "headers; the server replies with a status code (200 OK, 404 Not Found) and a body.",
    "sql injection": "SQL injection happens when user input is glued into a SQL string, letting an attacker change the "
                     "query. Prevent it with parameterised queries (placeholders), never string concatenation.",
    "xss": "Cross-site scripting (XSS) is when a site displays untrusted input as HTML/JS, so an attacker's script runs "
           "in other users' browsers. Prevent it by escaping output and using a Content-Security-Policy.",
    "normalization": "Normalisation organises tables to reduce duplicated data: 1NF atomic values, 2NF no partial "
                     "dependency on part of a key, 3NF no dependency between non-key columns.",
    "linux": "Linux is an operating-system kernel used on most servers. Core commands: `ls` list, `cd` move, `cat` view "
             "a file, `grep` search text, `chmod` change permissions, `man` read the manual.",
    "array": "An array/list stores items in order, each reachable by index in constant time. Inserting in the middle "
             "is slower because other items must shift.",
    "pandas": "pandas is a Python library for tables of data (DataFrames): load a CSV, filter rows, group and "
              "aggregate, and plot, all with a few lines.",
    "big o": "Big-O describes how running time grows with input size n, ignoring constants: O(1) constant, "
             "O(log n) binary search, O(n) one loop, O(n^2) nested loops.",
}


class LLMAdapter:
    """Interface for a future/optional LLM provider. Returns text or None (None => use fallback)."""
    def complete(self, system, user):
        return None


class HTTPAdapter(LLMAdapter):
    """Generic JSON-over-HTTPS adapter, active only when LLM_API_KEY and LLM_MODEL are set.
    Written for the Anthropic Messages API shape; NOT exercised by this repo's automated tests (needs a real key)."""
    url = "https://api.anthropic.com/v1/messages"

    def __init__(self, key, model):
        self.key, self.model = key, model

    def complete(self, system, user):
        body = json.dumps({"model": self.model, "max_tokens": 600, "system": system,
                           "messages": [{"role": "user", "content": user}]}).encode()
        req = urllib.request.Request(self.url, data=body, headers={
            "x-api-key": self.key, "anthropic-version": "2023-06-01", "content-type": "application/json"})
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        return data["content"][0]["text"]


def get_adapter():
    cfg = current_app.config
    if cfg.get("LLM_API_KEY") and cfg.get("LLM_MODEL"):
        return HTTPAdapter(cfg["LLM_API_KEY"], cfg["LLM_MODEL"])
    return LLMAdapter()


def _profile_line(uid):
    p = core.get_profile(uid)
    if not p:
        return "No profile yet."
    return (f"Student: {p['stream_name'] or 'stream not set'}, year {p['year'] or '?'}, goal "
            f"{p['career_title'] or 'not set'}, level {p['level']}, {p['minutes_per_day']} min/day, language {p['language']}.")


def reply(uid, mode, message):
    """Returns dict(text, source, links=[...]) - source is 'llm' or 'rules'."""
    message = (message or "").strip()[:500]
    mode = mode if mode in MODES else "explain"
    base = fallback(uid, mode, message)
    adapter = get_adapter()
    if type(adapter) is not LLMAdapter and mode in ("explain", "career"):
        try:
            text = adapter.complete(
                "You are NAVORA's study mentor for Indian college students. Be concise and accurate. " + _profile_line(uid),
                f"Mode: {mode}. Question: {message}")
            if text:
                base["text"], base["source"] = text, "llm"
        except Exception:                       # network, quota, parsing: always degrade gracefully
            base["note"] = "AI service unavailable - showing built-in guidance."
    return base


def fallback(uid, mode, message):
    fn = {"explain": _explain, "quiz": _quiz, "plan": _plan, "resources": _resources, "projects": _projects,
          "revision": _revision, "career": _career}[mode]
    out = fn(uid, message)
    out.setdefault("links", [])
    out["source"] = "rules"
    return out


def _find_topic(message):
    m = message.lower()
    for key in sorted(KB, key=len, reverse=True):
        if key in m:
            return key
    return None


def _skill_from_text(message):
    m = message.lower()
    for s in q("SELECT * FROM skills ORDER BY length(name) DESC"):
        if s["name"].lower() in m or s["slug"] in m:
            return s
    return None


def _explain(uid, message):
    key = _find_topic(message)
    if key:
        links = [{"label": r["title"], "url": f"/resources/{r['id']}"} for r in q(
            "SELECT id, title FROM resources WHERE lower(tags) LIKE ? OR lower(title) LIKE ? LIMIT 2", (f"%{key.split()[0]}%",) * 2)]
        return {"text": KB[key], "links": links}
    sk = _skill_from_text(message)
    if sk:
        return {"text": f"{sk['name']}: {sk['description']} I don't have a short built-in explanation for that exact "
                        f"question, but the resources below cover it.",
                "links": [{"label": r["title"], "url": f"/resources/{r['id']}"} for r in q(
                    "SELECT r.id, r.title FROM resources r JOIN resource_skills rs ON rs.resource_id=r.id "
                    "WHERE rs.skill_id=? AND r.pricing='free' LIMIT 3", (sk["id"],))]}
    return {"text": "I can explain these topics offline: " + ", ".join(sorted(KB)) +
                    ". Try e.g. 'Explain recursion'. Connect an LLM key (see docs/future-ai.md) for open-ended questions."}


def _quiz(uid, message):
    sk = _skill_from_text(message)
    prof = core.get_profile(uid)
    if not sk:
        gap = core.skill_gap(uid)
        sid = next((g["skill_id"] for g in gap if g["gap"] > 0), None)
        sk = q1("SELECT * FROM skills WHERE id=?", (sid,)) if sid else None
    where, args = ("WHERE q.skill_id=?", (sk["id"],)) if sk else ("", ())
    qs = q(f"SELECT q.*, s.name skill_name FROM quiz_questions q JOIN skills s ON s.id=q.skill_id {where}", args)
    if not qs:
        return {"text": "No quiz questions exist for that topic yet. Try 'Quiz me on Python' or 'Quiz me on SQL'."}
    pick = random.choice(qs)
    return {"text": f"Quick quiz on {pick['skill_name']}. Open the full quiz to answer and get your score.",
            "links": [{"label": f"Take the {pick['skill_name']} quiz", "url": f"/quiz/{pick['skill_id']}"}],
            "quiz": {"q": pick["question"]}}


def _plan(uid, message):
    import re
    m = re.search(r"(\d+(?:\.\d+)?)\s*(hour|hr|h|minute|min)", message.lower())
    minutes = core.get_profile(uid)["minutes_per_day"] if core.get_profile(uid) else 60
    if m:
        v = float(m.group(1))
        minutes = int(v * 60) if m.group(2).startswith(("h",)) else int(v)
    minutes = max(15, min(minutes, 600))
    nm = core.get_next_move(uid)
    blocks = []
    main = max(20, int(minutes * 0.6))
    blocks.append(f"{main} min - {nm['title']}" + (f" using \"{nm['resource']['resource']['title']}\"" if nm.get("resource") else ""))
    if minutes >= 45:
        blocks.append(f"{int(minutes * 0.25)} min - practise: write code / solve problems on what you just learned")
    blocks.append(f"{max(5, minutes - main - (int(minutes * 0.25) if minutes >= 45 else 0))} min - recap in your own words "
                  f"and note one question to look up")
    return {"text": f"Plan for {minutes} minutes:\n- " + "\n- ".join(blocks), "links": [{"label": "Open Your Next Move", "url": "/next"}]}


def _resources(uid, message):
    key = message.lower()
    sk = _skill_from_text(message)
    if sk:
        rs = q("SELECT r.id, r.title, r.pricing FROM resources r JOIN resource_skills rs ON rs.resource_id=r.id "
               "WHERE rs.skill_id=? AND r.status!='hidden' ORDER BY (r.pricing='free') DESC LIMIT 4", (sk["id"],))
    else:
        words = [w for w in key.split() if len(w) > 3][:3] or [key]
        rs = q("SELECT id, title, pricing FROM resources WHERE status!='hidden' AND (" +
               " OR ".join(["lower(title) LIKE ? OR lower(tags) LIKE ?"] * len(words)) + ") LIMIT 4",
               [f"%{w}%" for w in words for _ in (0, 1)])
    if not rs:
        return {"text": "I found no matching resources. Try the search page with a broader topic."}
    return {"text": "Here are some matches (free ones first):",
            "links": [{"label": f"{r['title']} ({r['pricing']})", "url": f"/resources/{r['id']}"} for r in rs]}


def _projects(uid, message):
    gap = core.skill_gap(uid)
    levels = core.user_skill_levels(uid)
    ps = q("SELECT p.id, p.title, p.difficulty, p.est_hours, ps.skill_id FROM projects p "
           "JOIN project_skills ps ON ps.project_id=p.id ORDER BY p.difficulty")
    fits = [p for p in ps if p["difficulty"] == core_diff(levels.get(p["skill_id"], 0))]
    focus = {g["skill_id"] for g in gap if g["gap"] > 0}
    fits.sort(key=lambda p: p["skill_id"] not in focus)
    fits = fits[:3] or list(ps[:3])
    return {"text": "Projects that match your current skill levels:",
            "links": [{"label": f"{p['title']} ({core.DIFF[p['difficulty']]}, ~{p['est_hours']}h)",
                       "url": f"/projects/{p['id']}"} for p in fits]}


def core_diff(level):
    return 1 if level < 35 else 2 if level < 70 else 3


def _revision(uid, message):
    done = q("SELECT r.title FROM learning_progress lp JOIN resources r ON r.id=lp.resource_id "
             "WHERE lp.user_id=? AND lp.status='completed' ORDER BY lp.completed_at DESC LIMIT 3", (uid,))
    weak = q("SELECT us.level, s.name FROM user_skills us JOIN skills s ON s.id=us.skill_id WHERE us.user_id=? "
             "ORDER BY us.level LIMIT 2", (uid,))
    lines = ["Day 1: re-read notes on " + (done[0]["title"] if done else "your latest topic"),
             "Day 3: 10 recall questions without looking (take a quiz)",
             "Day 7: explain the topic aloud, then redo anything you missed"]
    if weak:
        lines.append("Weakest skills right now: " + ", ".join(f"{w['name']} ({w['level']}%)" for w in weak))
    return {"text": "Spaced revision plan:\n- " + "\n- ".join(lines),
            "links": [{"label": "Exam preparation", "url": "/exam"}]}


def _career(uid, message):
    p = core.get_profile(uid)
    if not p or not p["career_id"]:
        return {"text": "You have not chosen a career goal. Try the guided discovery - it asks a few questions and "
                        "suggests several pathways.", "links": [{"label": "I don't know what to learn", "url": "/discover"}]}
    gap = [g for g in core.skill_gap(uid) if g["gap"] > 0]
    txt = f"Your goal is {p['career_title']}."
    txt += (" Biggest skill gaps: " + ", ".join(f"{g['name']} ({g['current']}% of {g['required']}%)" for g in gap[:3]) + "."
            if gap else " You meet the required level for all listed skills - focus on projects and portfolio.")
    return {"text": txt, "links": [{"label": "Skill gap", "url": "/skill-gap"}, {"label": "Career readiness", "url": "/readiness"}]}
