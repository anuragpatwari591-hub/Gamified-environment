# HTTP interface

NAVORA is server-rendered; the JSON endpoints below exist for the front-end. All state-changing requests need a CSRF token (`_csrf` form field or `X-CSRF-Token` header taken from `<meta name="csrf-token">`).

## JSON API

| Method & path | Auth | Description |
|---|---|---|
| `GET /api/health` | none | `{"status":"ok","resources":N}` |
| `GET /api/suggest?q=sq` | none | Up to 12 suggestions across skills, careers, resources. `q` < 2 chars returns `[]` |
| `GET /api/next` | login (401 otherwise) | `{title, reason, minutes, after, resource:{id,title,score}}` |
| `POST /api/mentor` | login, CSRF, 30/min | Body `{"mode":"explain|quiz|plan|resources|projects|revision|career","message":"..."}` -> `{text, links:[{label,url}], source:"rules"|"llm", note?}`. 400 on empty message, 429 when rate-limited |

## Pages (selected)

| Path | Purpose |
|---|---|
| `/`, `/discover`, `/resources`, `/resources/<id>`, `/compare?id=..`, `/careers`, `/careers/<slug>`, `/skills/<slug>`, `/streams/<slug>` | Public |
| `/go/<id>` | Tracked outbound redirect (affiliate-aware); `rel="sponsored"` in links |
| `/resources/<id>/report` (POST) | Report a broken link etc. (anonymous allowed, rate-limited) |
| `/onboarding`, `/dashboard`, `/next`, `/roadmap`, `/skill-gap`, `/projects`, `/progress`, `/bookmarks`, `/mentor`, `/quiz/<skill_id>`, `/semester`, `/exam`, `/readiness`, `/notifications`, `/profile` | Student (login) |
| `/resources/<id>/feedback`, `/review`, `/start`, `/complete`; `/bookmarks/toggle`; `/log-session`; `/stages/<id>/complete`; `/projects/<id>/status` | Student POST actions |
| `/admin/`, `/admin/e/<entity>[/new|/<id>|/<id>/delete]`, `/admin/users`, `/admin/reports`, `/admin/affiliates`, `/admin/feedback`, `/admin/audit`, `/admin/resources/<id>/verify` | Admin only (403 for students) |
| `/sitemap.xml`, `/robots.txt` | SEO |

Entities for `/admin/e/<entity>`: `resources, skills, careers, streams, roadmaps, stages, projects, sponsored, quiz`.
