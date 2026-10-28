"""JSON endpoints used by the front-end (and documented in docs/api.md)."""
from flask import Blueprint, g, jsonify, request

from ..db import q, scalar
from ..security import rate_limited
from ..services import core, mentor

bp = Blueprint("api", __name__, url_prefix="/api")


def _auth():
    if g.user is None:
        return jsonify(error="Authentication required"), 401
    return None


@bp.route("/health")
def health():
    return jsonify(status="ok", resources=scalar("SELECT COUNT(*) FROM resources"))


@bp.route("/mentor", methods=["POST"])
def mentor_api():
    if (e := _auth()):
        return e
    if rate_limited(f"mentor:{g.user['id']}", 30, 60):
        return jsonify(error="Too many messages. Please wait a moment."), 429
    data = request.get_json(silent=True) or {}
    msg = str(data.get("message", ""))[:500]
    if not msg.strip():
        return jsonify(error="Type a message first."), 400
    return jsonify(mentor.reply(g.user["id"], str(data.get("mode", "explain")), msg))


@bp.route("/next")
def next_api():
    if (e := _auth()):
        return e
    nm = core.get_next_move(g.user["id"])
    res = nm.get("resource")
    return jsonify(title=nm["title"], reason=nm["reason"], minutes=nm["minutes"], after=nm["after"],
                   resource=({"id": res["resource"]["id"], "title": res["resource"]["title"], "score": res["score"]} if res else None))


@bp.route("/suggest")
def suggest():
    text = request.args.get("q", "").strip().lower()[:40]
    if len(text) < 2:
        return jsonify([])
    like = f"%{text}%"
    out = [{"label": r["name"], "url": f"/skills/{r['slug']}", "type": "skill"} for r in q(
        "SELECT name, slug FROM skills WHERE lower(name) LIKE ? LIMIT 4", (like,))]
    out += [{"label": r["title"], "url": f"/careers/{r['slug']}", "type": "career"} for r in q(
        "SELECT title, slug FROM careers WHERE lower(title) LIKE ? LIMIT 3", (like,))]
    out += [{"label": r["title"], "url": f"/resources/{r['id']}", "type": "resource"} for r in q(
        "SELECT id, title FROM resources WHERE status!='hidden' AND lower(title) LIKE ? LIMIT 5", (like,))]
    return jsonify(out)
