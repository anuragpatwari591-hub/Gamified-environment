# Testing

```powershell
python -m pytest tests -q          # 84 tests, ~40 s
```

Each test builds a fresh seeded SQLite database in a temp folder, so tests are independent and never touch `instance/navora.db`.

## What is covered

| File | Area | Examples |
|---|---|---|
| `tests/test_auth_security.py` | Authentication & security | register/login/logout; invalid input; duplicate email (case-insensitive); generic login error; password hashed; CSRF required; login-required redirects; API 401; open-redirect blocked; student gets 403 on every admin URL; security headers & CSP; cookie flags; deactivated user loses session; login rate limit; SQL-injection and XSS payloads inert; error pages without stack traces |
| `tests/test_engine.py` | Recommendation engine (pure) | missing rating never invented; official > community credibility; freshness decay; learning style / difficulty / language / free-first change the ranking; sponsored/affiliate flags do **not** change score; every item has reasons; prerequisite caveat; feedback demotes the right resources; paid items get free alternatives; Next Move picks the first unfinished stage; weights are configurable |
| `tests/test_app_flows.py` | End-to-end flows | every public, demo and admin page renders (no tracebacks); onboarding validation; skill ratings change the Next Move; different goals give different Next Moves; search filters / empty / invalid / 5000-char queries; click and affiliate tracking; feedback changes `/api/next`; bookmarks (folder whitelist); reviews kept separate from external rating; report -> admin resolves; project status validation (rejects `javascript:` URLs); quiz scoring; semester & exam planner; readiness; mentor in all 7 modes offline; mentor falls back when the LLM endpoint is unreachable; discovery mode; compare (max 3, no "winner"); language switching and open-redirect safe; sponsored labelling; SEO endpoints; 404s |
| `tests/test_admin.py` | Admin | create/edit/delete resource with skills; validation (bad URL, empty title, invalid enum, non-numeric, out-of-range rating via DB constraint); duplicate slug handled; verify sets date; hidden resources disappear; cannot deactivate self; user search; affiliate conversion is manual; sponsored + stage management; CSRF on admin posts |

## Bugs found and fixed through testing

* `min_rating=oops` produced a SQL parameter-count mismatch (500) -> invalid numbers now ignore the filter.
* Test harness issue: logged-in clients can't fetch `/login`; tokens are now read from a public page.
* Compare page wording contained "winner" while promising not to pick one; reworded.

## Manual UI verification performed (Browser pane)

* Desktop 1280x900 and phone 375x812: landing page, demo dashboard, mentor, resources, resource detail, roadmap, compare, onboarding, semester, progress - **no horizontal overflow**, tab bar and burger menu appear on mobile.
* Onboarding stepper: all 7 steps, back/next, submit button on the last step.
* Mentor chat sends and renders a real answer through `/api/mentor`.
* Console: the only error was the app's own CSP refusing to be framed (which is the intended protection).

## Not covered / to do before a real launch

* No automated browser tests; accessibility was checked by construction (labels, focus styles, semantic landmarks, skip link, reduced-motion) but not with a screen reader or axe.
* No load testing; SQLite + in-memory rate limiting suit a single instance only.
* The real LLM adapter (`HTTPAdapter`) has never been called with a live key - only its failure path is tested.
* Link health: `python scripts/verify_links.py` checks *reachability only* (see its docstring). The last run found 68/74 reachable (several sites block scripts or timed out); none were 404 after retrying with GET. Content accuracy is not checked automatically.
