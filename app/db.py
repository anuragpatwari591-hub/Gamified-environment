"""Thin SQLite helper layer. All queries elsewhere use parameter binding (no string-built SQL values)."""
import sqlite3
from pathlib import Path

from flask import current_app, g

SCHEMA = Path(__file__).resolve().parent.parent / "database" / "schema.sql"


def get_db():
    if "db" not in g:
        path = current_app.config["DATABASE"]
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        g.db = sqlite3.connect(path)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(_exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def init_db():
    db = get_db()
    db.executescript(SCHEMA.read_text(encoding="utf-8"))
    db.commit()


def q(sql, args=()):
    return get_db().execute(sql, args).fetchall()


def q1(sql, args=()):
    return get_db().execute(sql, args).fetchone()


def scalar(sql, args=(), default=0):
    row = get_db().execute(sql, args).fetchone()
    return row[0] if row and row[0] is not None else default


def run(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur


def init_app(app):
    app.teardown_appcontext(close_db)
