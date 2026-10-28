# PROJECT_STATUS

_Last updated: 2026-10-28_

## Current state
NAVORA is a working, tested Flask application in `E:\QUANTUM COMPUTING PROJECT\navora\`. The parent folder holds an unrelated quantum-search project; it was left untouched. **Move `navora/` to its own folder before putting it on GitHub.**

* Run: see README quick start. 84/84 automated tests pass (`python -m pytest tests -q`).
* Seeded data: 74 real third-party resources, 33 skills, 18 streams, 10 careers with roadmaps, 24 projects, 34 quiz questions, a demo student and an admin account.
* Verified manually in the in-app browser: landing page, demo dashboard, mentor chat, onboarding stepper, and no horizontal overflow at 375 px on 8 key pages.

## Requirements coverage
| # | Requirement | State |
|---|---|---|
| 1-3 | Vision, differentiator, brand (NAVORA, logo, favicon, tokens) | Done. **Name not checked for trademark conflicts** (no web research done on this) |
| 4 | B.Tech-defensible stack | Done (Flask, SQLite, Jinja, plain JS) |
| 5, 33, 34 | Explainable engine, configurable weights, feedback loop | Done + unit-tested |
| 6 | Landing page, 15 sections | Done (testimonials section honestly says "Coming Soon") |
| 7, 8 | Onboarding (7 steps) & dashboard | Done |
| 9, 10, 11, 14, 15 | Resource directory, quality score, Why this?, Free-first, paid + free alternatives | Done |
| 12, 13, 47 | Roadmaps, Next Move | Done |
| 16, 58 | Monetisation architecture | Done as plumbing; **no real affiliates/sponsors** |
| 17 | AI Study Mentor (7 modes), LLM adapter | Done offline; **LLM path untested with a live key** |
| 18-20, 21 | Projects, skill gap, career explorer, readiness | Done |
| 22-26 | Progress, bookmarks, compare, semester, exam prep | Done (basic analytics, schedule and quizzes) |
| 27 | Multilingual UI (en/hi/bn) | Navigation, hero and dashboard strings only; most page text is English |
| 28 | Community | Architecture only (reviews/reports exist; no discussions) - intentionally not built |
| 29-31, 43-45 | Trust, admin, analytics, refresh, feedback, notifications | Done; notifications are in-app only |
| 32 | Database | 34 tables, constraints and indexes |
| 35-41 | Search, responsive, accessibility, performance, security, privacy, SEO | Done; accessibility not screen-reader/axe audited |
| 42 | Content seeding | Done, no seeded ratings or prices; Bengali resources: none yet |
| 48-50 | Discovery mode, gamification (light), demo mode | Done |
| 51-57 | Viva docs, tests, errors, GitHub prep, docs, presentation | Done (see docs/) |
| 63 PHASE 7 | GitHub | Done: local repo with logical commits, pushed to GitHub `main`; no secrets tracked (`.env`, `instance/`, `.venv` ignored) |
| 63 PHASE 8 | Deployment | **Not done / not verified**; Procfile and docs prepared |

## Known issues / honest gaps
* Resource `duration_min` values are editor estimates (UI says "about"); some are unknown.
* `last_verified_at` on seeded resources comes from an automated reachability check (`scripts/verify_links.py --apply`, 2026-10-28; 68/74 reachable, 6 blocked/timeouts need a manual check). It says nothing about content accuracy.
* Skill-level progress is a heuristic estimate.
* Rate limiter is in-memory/per-process; no email verification/password reset; no admin 2FA.
* Language switcher translates only a subset of strings.
* No screenshots committed in `docs/` (README mentions none); capture them before the presentation.
* Legal pages are drafts and need professional review before commercial use.

## Next tasks
1. Deploy (docs/deployment.md) and re-run `scripts/verify_links.py --apply`; have an admin manually verify resources.
2. Add Hindi/Bengali resources and translate more templates.
3. Accessibility audit (axe + screen reader); real browser tests.
4. Try the LLM adapter with a real key.

## Files / commands used
Created everything in the project root (app, seed, tests, docs, scripts). Commands: `python -m venv .venv`, `pip install flask pytest`, `python -m seed.seed --reset`, `python -m pytest tests -q`, `python scripts/verify_links.py [--apply]`, `python run.py`.

## Continuation protocol
If resuming: read this file, run `python -m pytest tests -q`, then work through "Next tasks".
