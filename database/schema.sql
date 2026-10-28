-- NAVORA relational schema (SQLite, 3NF-oriented). Foreign keys are enforced via PRAGMA foreign_keys=ON.

CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    email         TEXT NOT NULL UNIQUE COLLATE NOCASE,
    name          TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL DEFAULT 'student' CHECK (role IN ('student','admin')),
    is_active     INTEGER NOT NULL DEFAULT 1,
    is_demo       INTEGER NOT NULL DEFAULT 0,
    lang          TEXT NOT NULL DEFAULT 'en',
    created_at    TEXT NOT NULL DEFAULT (datetime('now')),
    last_login_at TEXT
);

CREATE TABLE IF NOT EXISTS streams (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    slug  TEXT NOT NULL UNIQUE,
    name  TEXT NOT NULL,
    group_name TEXT NOT NULL DEFAULT 'Other',
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS skills (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT NOT NULL UNIQUE,
    name        TEXT NOT NULL,
    category    TEXT NOT NULL DEFAULT 'Technology',
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS careers (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    interest_tags TEXT NOT NULL DEFAULT '',        -- comma separated, used by discovery mode
    degree_backgrounds TEXT NOT NULL DEFAULT '',
    certifications TEXT NOT NULL DEFAULT '',
    portfolio_requirements TEXT NOT NULL DEFAULT '',
    interview_prep TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS career_skills (
    career_id      INTEGER NOT NULL REFERENCES careers(id) ON DELETE CASCADE,
    skill_id       INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    required_level INTEGER NOT NULL DEFAULT 60 CHECK (required_level BETWEEN 0 AND 100),
    PRIMARY KEY (career_id, skill_id)
);

CREATE TABLE IF NOT EXISTS profiles (
    user_id        INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
    stream_id      INTEGER REFERENCES streams(id),
    specialization TEXT NOT NULL DEFAULT '',
    college        TEXT NOT NULL DEFAULT '',
    year           INTEGER CHECK (year BETWEEN 1 AND 6),
    semester       INTEGER CHECK (semester BETWEEN 1 AND 12),
    career_id      INTEGER REFERENCES careers(id),
    level          TEXT NOT NULL DEFAULT 'beginner' CHECK (level IN ('beginner','intermediate','advanced')),
    minutes_per_day INTEGER NOT NULL DEFAULT 60 CHECK (minutes_per_day BETWEEN 10 AND 600),
    language       TEXT NOT NULL DEFAULT 'English',
    budget         TEXT NOT NULL DEFAULT 'mostly_free' CHECK (budget IN ('free','mostly_free','paid_ok','premium')),
    free_first     INTEGER NOT NULL DEFAULT 1,
    onboarded      INTEGER NOT NULL DEFAULT 0,
    updated_at     TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS user_interests (
    user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    interest TEXT NOT NULL,
    PRIMARY KEY (user_id, interest)
);

CREATE TABLE IF NOT EXISTS user_formats (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    format  TEXT NOT NULL,
    PRIMARY KEY (user_id, format)
);

CREATE TABLE IF NOT EXISTS user_skills (
    user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    skill_id INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    level    INTEGER NOT NULL DEFAULT 0 CHECK (level BETWEEN 0 AND 100),
    PRIMARY KEY (user_id, skill_id)
);

CREATE TABLE IF NOT EXISTS resources (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    title         TEXT NOT NULL,
    provider      TEXT NOT NULL,
    url           TEXT NOT NULL,
    source_url    TEXT NOT NULL DEFAULT '',
    category      TEXT NOT NULL DEFAULT 'Technology',
    topic         TEXT NOT NULL DEFAULT '',
    resource_type TEXT NOT NULL DEFAULT 'course' CHECK (resource_type IN
                  ('course','video','documentation','book','article','practice','project','github','certification')),
    format        TEXT NOT NULL DEFAULT 'reading' CHECK (format IN
                  ('video','reading','interactive','practice','project')),
    source_kind   TEXT NOT NULL DEFAULT 'community' CHECK (source_kind IN
                  ('official','university','government','nonprofit','platform','community')),
    difficulty    INTEGER NOT NULL DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 3),
    duration_min  INTEGER CHECK (duration_min IS NULL OR duration_min > 0),
    language      TEXT NOT NULL DEFAULT 'English',
    pricing       TEXT NOT NULL DEFAULT 'free' CHECK (pricing IN ('free','freemium','paid')),
    price_inr     INTEGER CHECK (price_inr IS NULL OR price_inr >= 0),
    price_note    TEXT NOT NULL DEFAULT '',
    rating        REAL CHECK (rating IS NULL OR rating BETWEEN 0 AND 5),
    rating_count  INTEGER CHECK (rating_count IS NULL OR rating_count >= 0),
    rating_source TEXT NOT NULL DEFAULT '',
    description   TEXT NOT NULL DEFAULT '',
    prerequisites TEXT NOT NULL DEFAULT '',
    strengths     TEXT NOT NULL DEFAULT '',
    limitations   TEXT NOT NULL DEFAULT '',
    suitable_for  TEXT NOT NULL DEFAULT '',
    tags          TEXT NOT NULL DEFAULT '',
    affiliate_url TEXT NOT NULL DEFAULT '',
    affiliate_ref TEXT NOT NULL DEFAULT '',
    commission_pct REAL,
    status        TEXT NOT NULL DEFAULT 'unverified' CHECK (status IN ('unverified','active','broken','outdated','hidden')),
    last_verified_at TEXT,
    verification_notes TEXT NOT NULL DEFAULT '',
    created_at    TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX IF NOT EXISTS idx_resources_status ON resources(status);
CREATE INDEX IF NOT EXISTS idx_resources_pricing ON resources(pricing);
CREATE INDEX IF NOT EXISTS idx_resources_category ON resources(category);

CREATE TABLE IF NOT EXISTS resource_skills (
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    skill_id    INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    PRIMARY KEY (resource_id, skill_id)
);
CREATE INDEX IF NOT EXISTS idx_resource_skills_skill ON resource_skills(skill_id);

CREATE TABLE IF NOT EXISTS roadmaps (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    career_id   INTEGER NOT NULL UNIQUE REFERENCES careers(id) ON DELETE CASCADE,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS roadmap_stages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    roadmap_id  INTEGER NOT NULL REFERENCES roadmaps(id) ON DELETE CASCADE,
    position    INTEGER NOT NULL,
    title       TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    concepts    TEXT NOT NULL DEFAULT '',
    skill_id    INTEGER REFERENCES skills(id),
    target_level INTEGER NOT NULL DEFAULT 60 CHECK (target_level BETWEEN 1 AND 100),
    est_hours   INTEGER NOT NULL DEFAULT 10 CHECK (est_hours > 0),
    milestone   TEXT NOT NULL DEFAULT '',
    UNIQUE (roadmap_id, position)
);

CREATE TABLE IF NOT EXISTS user_stages (
    user_id  INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    stage_id INTEGER NOT NULL REFERENCES roadmap_stages(id) ON DELETE CASCADE,
    completed_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, stage_id)
);

CREATE TABLE IF NOT EXISTS projects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    slug        TEXT NOT NULL UNIQUE,
    title       TEXT NOT NULL,
    difficulty  INTEGER NOT NULL DEFAULT 1 CHECK (difficulty BETWEEN 1 AND 3),
    est_hours   INTEGER NOT NULL DEFAULT 5 CHECK (est_hours > 0),
    description TEXT NOT NULL DEFAULT '',
    outcomes    TEXT NOT NULL DEFAULT '',
    technologies TEXT NOT NULL DEFAULT '',
    checklist   TEXT NOT NULL DEFAULT '',
    portfolio_blurb TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS project_skills (
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    skill_id   INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    PRIMARY KEY (project_id, skill_id)
);

CREATE TABLE IF NOT EXISTS user_projects (
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    project_id INTEGER NOT NULL REFERENCES projects(id) ON DELETE CASCADE,
    status     TEXT NOT NULL DEFAULT 'started' CHECK (status IN ('started','completed')),
    repo_url   TEXT NOT NULL DEFAULT '',
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, project_id)
);

CREATE TABLE IF NOT EXISTS learning_progress (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    status      TEXT NOT NULL DEFAULT 'started' CHECK (status IN ('started','completed')),
    started_at  TEXT NOT NULL DEFAULT (datetime('now')),
    completed_at TEXT,
    PRIMARY KEY (user_id, resource_id)
);

CREATE TABLE IF NOT EXISTS study_sessions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resource_id INTEGER REFERENCES resources(id) ON DELETE SET NULL,
    topic       TEXT NOT NULL DEFAULT '',
    minutes     INTEGER NOT NULL CHECK (minutes BETWEEN 1 AND 720),
    day         TEXT NOT NULL,
    is_demo     INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_sessions_user_day ON study_sessions(user_id, day);

CREATE TABLE IF NOT EXISTS bookmarks (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind      TEXT NOT NULL CHECK (kind IN ('resource','project','roadmap')),
    ref_id    INTEGER NOT NULL,
    folder    TEXT NOT NULL DEFAULT 'Learn Later' CHECK (folder IN ('Learn Later','Projects','Interview','Semester','Career')),
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE (user_id, kind, ref_id)
);

CREATE TABLE IF NOT EXISTS quiz_questions (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    skill_id  INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    question  TEXT NOT NULL,
    option_a  TEXT NOT NULL,
    option_b  TEXT NOT NULL,
    option_c  TEXT NOT NULL,
    option_d  TEXT NOT NULL,
    answer    TEXT NOT NULL CHECK (answer IN ('a','b','c','d')),
    explanation TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS quiz_attempts (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id   INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    skill_id  INTEGER NOT NULL REFERENCES skills(id) ON DELETE CASCADE,
    score     INTEGER NOT NULL,
    total     INTEGER NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS recommendation_feedback (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    useful      INTEGER NOT NULL CHECK (useful IN (0,1)),
    reason      TEXT NOT NULL DEFAULT '' CHECK (reason IN ('','too_difficult','too_long','boring','wrong_topic',
                'already_knew','wrong_style','not_relevant')),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS resource_reviews (
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    rating      INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    difficulty_feedback TEXT NOT NULL DEFAULT '' CHECK (difficulty_feedback IN ('','too_easy','just_right','too_hard')),
    review      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT (datetime('now')),
    PRIMARY KEY (user_id, resource_id)
);

CREATE TABLE IF NOT EXISTS resource_clicks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    pricing     TEXT NOT NULL,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS affiliate_clicks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    ref_id      TEXT NOT NULL DEFAULT '',
    converted   INTEGER NOT NULL DEFAULT 0,       -- only set by an admin after a partner report confirms it
    commission_inr REAL NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS sponsored_content (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT NOT NULL,
    sponsor     TEXT NOT NULL,
    resource_id INTEGER REFERENCES resources(id) ON DELETE SET NULL,
    url         TEXT NOT NULL DEFAULT '',
    blurb       TEXT NOT NULL DEFAULT '',
    is_demo     INTEGER NOT NULL DEFAULT 0,
    active      INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS reports (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    resource_id INTEGER NOT NULL REFERENCES resources(id) ON DELETE CASCADE,
    user_id     INTEGER REFERENCES users(id) ON DELETE SET NULL,
    kind        TEXT NOT NULL CHECK (kind IN ('broken_link','outdated','misleading','wrong_category','wrong_price')),
    note        TEXT NOT NULL DEFAULT '',
    status      TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','resolved','dismissed')),
    created_at  TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS notifications (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL DEFAULT 'info',
    message    TEXT NOT NULL,
    is_read    INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS search_log (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    query      TEXT NOT NULL,
    results    INTEGER NOT NULL DEFAULT 0,
    user_id    INTEGER REFERENCES users(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS semester_subjects (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    name        TEXT NOT NULL,
    exam_date   TEXT,
    is_weak     INTEGER NOT NULL DEFAULT 0,
    target_marks INTEGER CHECK (target_marks IS NULL OR target_marks BETWEEN 0 AND 100),
    hours_per_week INTEGER NOT NULL DEFAULT 4 CHECK (hours_per_week BETWEEN 0 AND 80)
);

CREATE TABLE IF NOT EXISTS syllabus_topics (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id INTEGER NOT NULL REFERENCES semester_subjects(id) ON DELETE CASCADE,
    topic      TEXT NOT NULL,
    done       INTEGER NOT NULL DEFAULT 0,
    is_weak    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS readiness_items (
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    item    TEXT NOT NULL,
    done    INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (user_id, item)
);

CREATE TABLE IF NOT EXISTS audit_logs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    admin_id   INTEGER REFERENCES users(id) ON DELETE SET NULL,
    action     TEXT NOT NULL,
    target     TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
