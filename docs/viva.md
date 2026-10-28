# B.Tech project report notes & viva preparation

## 1. Problem statement
Students from every stream face an overload of online learning content. They lack (a) an order to learn things in, (b) a reason to pick one resource over another, and (c) a link between what they study and the career they want. Existing course marketplaces optimise for catalogue size and sales, not for the student's next useful action.

## 2. Existing system
Search engines, YouTube, MOOC marketplaces and "roadmap" websites: static, not personalised to stream/semester/learning style, unclear ranking (often commercially influenced), few honest quality signals.

## 3. Proposed system
NAVORA: a personal learning navigator. Student profile ("Learning DNA") -> career goal -> skill gap -> roadmap -> *explained* free-first recommendations -> projects -> progress -> career readiness, with a single "Your Next Move".

## 4. Objectives
1. Reduce decision effort to one clear next action. 2. Explain every recommendation. 3. Put free, official resources first. 4. Keep commercial content separate and disclosed. 5. Support non-engineering streams. 6. Stay explainable and reproducible at B.Tech level.

## 5. Functional requirements
Registration/login; Learning DNA onboarding; dashboard; Next Move; roadmap; skill gap; resource search/filter/compare; quality score; feedback/review/report; projects & quizzes; bookmarks; progress tracking; mentor chat; semester/exam planner; career readiness; admin CRUD, verification, analytics; affiliate/sponsored tracking.

## 6. Non-functional requirements
Security (hashing, CSRF, CSP, rate limiting); usability and accessibility (labels, focus, keyboard, skip link); responsiveness (desktop to 375 px); performance (small SQLite DB, indexed queries, no heavy frameworks); maintainability (modular, tested); honesty/trust (no fabricated data); graceful degradation (AI optional).

## 7. Architecture, diagrams
See [architecture.md](architecture.md) (layers, use cases, DFD), [database.md](database.md) (ER diagram, normalisation), [recommendation-engine.md](recommendation-engine.md).

## 8. Authentication & security
Werkzeug salted `scrypt` hashes; server-side signed session cookie (HTTP-only, SameSite); CSRF tokens; role check (student/admin) via decorators and a blueprint guard; see [security.md](security.md).

## 9. Testing
84 automated pytest tests + manual UI checks; see [testing.md](testing.md).

## 10. Limitations
Single-instance rate limiter; SQLite; no email/password reset; resource durations are editor estimates; ratings not yet populated (shown as unavailable); link checker verifies reachability, not content; Bengali content limited; skill levels are estimates; legal pages need professional review; not deployed.

## 11. Future scope
Real LLM mentor, learned ranking from feedback, automated resource refresh, verified assessments, mobile app, institutional dashboards, premium features (see [future-ai.md](future-ai.md), [business-model.md](business-model.md)).

## 12. Deployment & business model
[deployment.md](deployment.md), [business-model.md](business-model.md) (potential vs actual revenue clearly separated).

---

## Viva question bank (with short answers)

**Why Flask and not Django?** Flask is minimal, so each part (routing, templates, DB access, security) is visible and explainable; Django hides much behind its ORM/admin.

**Why SQLite? Can it scale?** Zero-setup, file-based, reproducible for demos. For many concurrent writers move to MySQL/PostgreSQL; only `app/db.py` and a few upsert statements change.

**Why no ORM?** To show the SQL explicitly and keep the dependency list to Flask only.

**How does the recommendation work?** A weighted average of 12 normalised components (career relevance, skill relevance, prerequisites, style, difficulty, language, time, quality, freshness, budget, interests, free-first); weights in JSON. Each component also yields a sentence for the explanation.

**Is this machine learning?** No. It is an explainable rule/score-based recommender. It "learns" only in the sense that stored feedback adjusts scores. A future version could fit weights from data.

**How do you avoid commercial bias?** Sponsored/affiliate flags are not inputs to the score (unit-tested); sponsored content is a separate labelled box; paid items always show free alternatives.

**How do you handle missing ratings?** `rating` is nullable; the quality score drops missing signals and renormalises; UI says "Rating unavailable". External rating and NAVORA reviews are never mixed.

**How is the skill level computed?** Self-rating + completed resources (+10..15) + completed projects (+15) + quizzes (raise only, cap 80). It is an estimate and labelled so.

**What stops SQL injection?** Parameterised queries everywhere; dynamic fragments come from fixed whitelists.

**What is CSRF and how do you prevent it?** A forged cross-site request using the victim's cookie. We require a secret per-session token on every state-changing request.

**How are passwords stored?** Salted scrypt hashes via Werkzeug; verification uses constant-time comparison; unknown emails do a dummy hash check to avoid timing leaks.

**How does the AI mentor work without an API?** Rule-based answers from a small knowledge base plus database lookups (next move, skill gap, quizzes, resources). If an LLM key is configured it augments Explain/Career; any failure falls back.

**What is normalisation? Show an example.** Removing redundancy: `resource_skills(resource_id, skill_id)` instead of a comma list of skills in `resources` (1NF/2NF); user interests are rows in `user_interests`.

**Explain a deliberate denormalisation.** `resources.tags` and `careers.interest_tags` are free-text for editors and are never joined.

**What happens if a resource link breaks?** Users can report it; admins review reports, set status (`broken`, `hidden`), and mark manual verification. A script checks reachability.

**How do you ensure accessibility?** Semantic landmarks, labelled inputs, visible focus, skip link, keyboard-operable controls, `prefers-reduced-motion`, readable contrast in light/dark.

**What are the trade-offs of in-memory rate limiting?** Simple, no infrastructure; but per-process and lost on restart. Production: Redis.

**What would you do with more time?** Real deployment, email verification, learned ranking from feedback, axe/screen-reader audit, more curated Hindi/Bengali content, Postgres.

**Difference between "Demo Data" and real data?** Demo student activity and the sample sponsor are illustrative and labelled; the catalogue is real, attributed third-party resources.
