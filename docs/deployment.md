# Deployment

**Status: not deployed.** No hosting credentials were available, so nothing here has been verified on a live host. The project is prepared so deployment needs only configuration.

## What a host needs

* Python 3.10+, `pip install -r requirements.txt`
* A persistent disk path for the SQLite file (`DATABASE_PATH`), **or** migrate to MySQL (see docs/database.md)
* Environment variables: `SECRET_KEY` (required, long random), `COOKIE_SECURE=1` (HTTPS), `SITE_URL`, `ADMIN_EMAIL`, `ADMIN_PASSWORD`
* Start command: `gunicorn run:app --bind 0.0.0.0:$PORT --workers 2` (see `Procfile`)

## First deploy

```bash
pip install -r requirements.txt
python -m seed.seed          # once; prints the admin password if ADMIN_PASSWORD is unset
gunicorn run:app
```

## Example: PythonAnywhere / any WSGI host

1. Upload the repo, create a virtualenv, `pip install -r requirements.txt`.
2. Set env vars (or a `.env` file outside the web root).
3. Point the WSGI file at `from run import app as application`.
4. Run `python -m seed.seed` in a console. Enable HTTPS and set `COOKIE_SECURE=1`.

## Example: Render / Railway / Fly (Procfile-based)

Create a web service from the repo, build command `pip install -r requirements.txt`, start command from the Procfile, attach a persistent disk mounted where `DATABASE_PATH` points, add env vars, then run the seed once in a shell.

## Production checklist

- [ ] `SECRET_KEY` set (otherwise sessions reset on every restart)
- [ ] HTTPS on, `COOKIE_SECURE=1`
- [ ] Admin password changed/stored securely; demo account policy decided
- [ ] DB file on persistent storage and backed up
- [ ] `FLASK_DEBUG` unset
- [ ] Single worker or move rate limiting to Redis (the in-memory limiter is per process)
- [ ] Legal pages reviewed by a professional
- [ ] `python scripts/verify_links.py --apply` run, resources reviewed by an admin
