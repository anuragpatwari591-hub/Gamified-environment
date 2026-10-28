"""Development entry point:  python run.py   (production: gunicorn 'run:app')"""
import os

from app import create_app
from app.db import get_db, init_db

app = create_app()

with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=os.environ.get("FLASK_DEBUG") == "1")
