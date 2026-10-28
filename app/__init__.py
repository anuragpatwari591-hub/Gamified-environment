"""NAVORA application factory."""
from datetime import date

from flask import Flask, g, render_template, request, session

from config import Config

from . import db, i18n, security


def create_app(overrides=None):
    app = Flask(__name__)
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    db.init_app(app)

    app.before_request(security.load_user)
    app.before_request(security.csrf_protect)
    app.after_request(security.add_headers)

    @app.context_processor
    def inject():
        lang = (g.user["lang"] if g.get("user") else session.get("lang")) or "en"
        return {
            "t": lambda k: i18n.translate(lang, k), "lang": lang, "LANGS": i18n.LANGS,
            "csrf_token": security.csrf_token, "user": g.get("user"), "year": date.today().year,
            "unread": _unread(),
        }

    def _unread():
        if g.get("user"):
            return db.scalar("SELECT COUNT(*) FROM notifications WHERE user_id=? AND is_read=0", (g.user["id"],))
        return 0

    from .routes import admin, api, auth, learner, main
    for bp in (main.bp, auth.bp, learner.bp, admin.bp, api.bp):
        app.register_blueprint(bp)

    @app.errorhandler(400)
    def e400(e):
        return render_template("error.html", code=400, title="That request didn't look right",
                               msg=getattr(e, "description", "")), 400

    @app.errorhandler(403)
    def e403(e):
        return render_template("error.html", code=403, title="You don't have access to this page",
                               msg="This area is restricted. If you think this is a mistake, sign in with the right account."), 403

    @app.errorhandler(404)
    def e404(e):
        return render_template("error.html", code=404, title="We couldn't find that page",
                               msg="The link may be old or mistyped. Let's get you back on track."), 404

    @app.errorhandler(413)
    def e413(e):
        return render_template("error.html", code=413, title="That was too much data", msg="Please send less text."), 413

    @app.errorhandler(429)
    def e429(e):
        return render_template("error.html", code=429, title="Slow down a little",
                               msg="Too many attempts. Please wait a minute and try again."), 429

    @app.errorhandler(500)
    def e500(e):
        app.logger.exception("Unhandled error")        # details go to the server log only, never to the user
        return render_template("error.html", code=500, title="Something went wrong on our side",
                               msg="We've logged it. Please try again in a moment."), 500

    @app.cli.command("init-db")
    def init_db_cmd():
        db.init_db()
        print("Database initialised.")

    return app
