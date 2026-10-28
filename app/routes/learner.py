"""Signed-in student experience."""
from datetime import date, datetime, timedelta

from flask import Blueprint, abort, current_app, flash, g, jsonify, redirect, render_template, request, url_for

from ..db import get_db, q, q1, run, scalar
from ..recommendation import engine
from ..security import login_required
from ..services import core, mentor

bp = Blueprint("learner", __name__)


def uid():
    return g.user["id"]


def _int(v, lo, hi, default=None):
    try:
        n = int(v)
    except (TypeError, ValueError):
        return default
    return n if lo <= n <= hi else default


# ------------------------------------------------------------ onboarding / profile
def _onboard_data():
    return {"streams": q("SELECT * FROM streams ORDER BY group_name, name"), "careers": q("SELECT * FROM careers ORDER BY title"),
            "interests": core.INTERESTS, "formats": core.FORMATS, "languages": core.LANGUAGES, "budgets": core.BUDGETS}


def _save_profile(form):
    """Validate and persist the Learning DNA. Returns list of errors."""
    errors = []
    stream = _int(form.get("stream_id"), 1, 10 ** 6)
    if stream is None or not q1("SELECT 1 FROM streams WHERE id=?", (stream,)):
        errors.append("Choose your stream or degree.")
    year = _int(form.get("year"), 1, 6)
    sem = _int(form.get("semester"), 1, 12)
    career = _int(form.get("career_id"), 1, 10 ** 6)
    if career is not None and not q1("SELECT 1 FROM careers WHERE id=?", (career,)):
        career = None
    level = form.get("level", "beginner")
    if level not in ("beginner", "intermediate", "advanced"):
        errors.append("Choose a valid skill level.")
    minutes = _int(form.get("minutes_per_day"), 10, 600)
    if minutes is None:
        errors.append("Choose how much time you can study per day.")
    lang = form.get("language", "English")
    if lang not in core.LANGUAGES:
        lang = "English"
    budget = form.get("budget", "mostly_free")
    if budget not in core.BUDGETS:
        errors.append("Choose a budget preference.")
    interests = [i for i in form.getlist("interests") if i in core.INTERESTS]
    formats = [f for f in form.getlist("formats") if f in core.FORMATS]
    if errors:
        return errors
    run("""INSERT INTO profiles(user_id, stream_id, specialization, college, year, semester, career_id, level,
               minutes_per_day, language, budget, free_first, onboarded, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,1,datetime('now'))
           ON CONFLICT(user_id) DO UPDATE SET stream_id=excluded.stream_id, specialization=excluded.specialization,
               college=excluded.college, year=excluded.year, semester=excluded.semester, career_id=excluded.career_id,
               level=excluded.level, minutes_per_day=excluded.minutes_per_day, language=excluded.language,
               budget=excluded.budget, free_first=excluded.free_first, onboarded=1, updated_at=datetime('now')""",
        (uid(), stream, form.get("specialization", "").strip()[:80], form.get("college", "").strip()[:120], year, sem,
         career, level, minutes, lang, budget, 1 if (form.get("free_first") or budget in ("free", "mostly_free")) else 0))
    db = get_db()
    db.execute("DELETE FROM user_interests WHERE user_id=?", (uid(),))
    db.executemany("INSERT INTO user_interests VALUES (?,?)", [(uid(), i) for i in interests])
    db.execute("DELETE FROM user_formats WHERE user_id=?", (uid(),))
    db.executemany("INSERT INTO user_formats VALUES (?,?)", [(uid(), f) for f in formats])
    db.commit()
    return []


@bp.route("/onboarding", methods=["GET", "POST"])
@login_required
def onboarding():
    if request.method == "POST":
        errs = _save_profile(request.form)
        if errs:
            for e in errs:
                flash(e, "error")
            mine = {"interests": set(request.form.getlist("interests")), "formats": set(request.form.getlist("formats"))}
            return render_template("onboarding.html", p=request.form, form=request.form, mine=mine, **_onboard_data()), 400
        flash("Your Learning DNA is saved. Rate your current skills so we can build an accurate roadmap.", "ok")
        return redirect(url_for("learner.skill_gap") if not core.user_skill_levels(uid()) else url_for("learner.dashboard"))
    return render_template("onboarding.html", p=core.get_profile(uid()), form={}, mine=_mine(), **_onboard_data())


@bp.route("/profile", methods=["GET", "POST"])
@login_required
def profile():
    if request.method == "POST":
        errs = _save_profile(request.form)
        for e in errs:
            flash(e, "error")
        if not errs:
            flash("Learning DNA updated.", "ok")
            return redirect(url_for("learner.profile"))
        return render_template("profile.html", p=core.get_profile(uid()), form=request.form, mine=_mine(), **_onboard_data()), 400
    return render_template("profile.html", p=core.get_profile(uid()), form={}, mine=_mine(), **_onboard_data())


def _mine():
    return {"interests": {r["interest"] for r in q("SELECT interest FROM user_interests WHERE user_id=?", (uid(),))},
            "formats": {r["format"] for r in q("SELECT format FROM user_formats WHERE user_id=?", (uid(),))}}


def _need_onboarding():
    p = core.get_profile(uid())
    return None if p and p["onboarded"] else redirect(url_for("learner.onboarding"))


# ------------------------------------------------------------ dashboard & next move
@bp.route("/dashboard")
@login_required
def dashboard():
    if (r := _need_onboarding()):
        return r
    p = core.get_profile(uid())
    nm = core.get_next_move(uid())
    ctx = core.build_context(uid())
    recs = engine.rank(core.all_resources(), ctx, limit=5)
    rm, stages = core.roadmap_stages(uid(), p["career_id"])
    skills = q("SELECT s.name, us.level FROM user_skills us JOIN skills s ON s.id=us.skill_id WHERE us.user_id=? "
               "ORDER BY us.level DESC LIMIT 6", (uid(),))
    cont = q("SELECT r.id, r.title, r.provider, r.duration_min FROM learning_progress lp JOIN resources r ON r.id=lp.resource_id "
             "WHERE lp.user_id=? AND lp.status='started' ORDER BY lp.started_at DESC LIMIT 3", (uid(),))
    snap = core.learning_snapshot(uid())
    hour = datetime.now().hour
    greet = "Good morning" if hour < 12 else "Good afternoon" if hour < 17 else "Good evening"
    upcoming = [s for s in stages if not s["done"]][:3]
    exams = q("SELECT name, exam_date FROM semester_subjects WHERE user_id=? AND exam_date >= ? ORDER BY exam_date LIMIT 2",
              (uid(), date.today().isoformat()))
    prog_projects = q("SELECT p.id, p.title FROM user_projects up JOIN projects p ON p.id=up.project_id "
                      "WHERE up.user_id=? AND up.status='started' LIMIT 2", (uid(),))
    sponsored = q("SELECT * FROM sponsored_content WHERE active=1 LIMIT 1")
    return render_template("dashboard.html", p=p, nm=nm, recs=recs, stages=stages, skills=skills, cont=cont, snap=snap,
                           greet=greet, upcoming=upcoming, exams=exams, prog_projects=prog_projects, sponsored=sponsored,
                           reasons=core.FEEDBACK_REASONS, level_label=core.level_label, is_demo=bool(g.user["is_demo"]))


@bp.route("/next")
@login_required
def next_move():
    if (r := _need_onboarding()):
        return r
    nm = core.get_next_move(uid())
    return render_template("next.html", nm=nm, reasons=core.FEEDBACK_REASONS)


# ------------------------------------------------------------ roadmap, skill gap
@bp.route("/roadmap")
@login_required
def roadmap():
    if (r := _need_onboarding()):
        return r
    p = core.get_profile(uid())
    rm, stages = core.roadmap_stages(uid(), p["career_id"])
    detail = []
    pool = core.all_resources()
    ctx = core.build_context(uid())
    for s in stages:
        cand = [r for r in pool if s["skill_id"] in r["skill_ids"]]
        ctx2 = dict(ctx, focus_skill_ids={s["skill_id"]} if s["skill_id"] else set())
        top = engine.rank(cand, ctx2, limit=3, exclude_completed=False) if cand else []
        proj = q1("SELECT p.id, p.title FROM projects p JOIN project_skills ps ON ps.project_id=p.id WHERE ps.skill_id=? "
                  "ORDER BY p.difficulty LIMIT 1", (s["skill_id"],)) if s["skill_id"] else None
        qz = scalar("SELECT COUNT(*) FROM quiz_questions WHERE skill_id=?", (s["skill_id"],)) if s["skill_id"] else 0
        detail.append({"stage": s, "top": top, "project": proj, "quiz": qz})
    done_h = sum(s["est_hours"] for s in stages if s["done"])
    total_h = sum(s["est_hours"] for s in stages) or 1
    return render_template("roadmap.html", p=p, rm=rm, detail=detail, pct=round(100 * done_h / total_h),
                           total_h=total_h, done_h=done_h)


@bp.route("/stages/<int:sid>/complete", methods=["POST"])
@login_required
def stage_complete(sid):
    st = q1("SELECT * FROM roadmap_stages WHERE id=?", (sid,))
    if not st:
        abort(404)
    if request.form.get("undo"):
        run("DELETE FROM user_stages WHERE user_id=? AND stage_id=?", (uid(), sid))
    else:
        run("INSERT OR IGNORE INTO user_stages(user_id, stage_id) VALUES (?,?)", (uid(), sid))
        core.check_stage_milestones(uid())
    return redirect(url_for("learner.roadmap") + f"#stage-{sid}")


@bp.route("/skill-gap", methods=["GET", "POST"])
@login_required
def skill_gap():
    if (r := _need_onboarding()):
        return r
    if request.method == "POST":
        db = get_db()
        for key, val in request.form.items():
            if key.startswith("skill_"):
                sid, lvl = _int(key[6:], 1, 10 ** 6), _int(val, 0, 100)
                if sid and lvl is not None and q1("SELECT 1 FROM skills WHERE id=?", (sid,)):
                    db.execute("INSERT INTO user_skills VALUES (?,?,?) ON CONFLICT(user_id, skill_id) DO UPDATE SET level=excluded.level",
                               (uid(), sid, lvl))
        db.commit()
        flash("Skill levels saved. Your roadmap and gaps are updated.", "ok")
        return redirect(url_for("learner.skill_gap"))
    p = core.get_profile(uid())
    gap = core.skill_gap(uid())
    missing = [g_ for g_ in gap if g_["gap"] > 0]
    order = []
    for g_ in missing:
        r = engine.rank([x for x in core.all_resources() if g_["skill_id"] in x["skill_ids"]], core.build_context(uid()), limit=1)
        order.append({"gap": g_, "res": r[0] if r else None})
    return render_template("skill_gap.html", p=p, gap=gap, order=order, level_label=core.level_label)


# ------------------------------------------------------------ progress, resources actions
@bp.route("/resources/<int:rid>/start", methods=["POST"])
@login_required
def res_start(rid):
    if not q1("SELECT 1 FROM resources WHERE id=?", (rid,)):
        abort(404)
    run("INSERT OR IGNORE INTO learning_progress(user_id, resource_id) VALUES (?,?)", (uid(), rid))
    flash("Added to Continue Learning.", "ok")
    return redirect(request.referrer or url_for("main.resource_detail", rid=rid))


@bp.route("/resources/<int:rid>/complete", methods=["POST"])
@login_required
def res_complete(rid):
    if not core.complete_resource(uid(), rid):
        abort(404)
    mins = _int(request.form.get("minutes"), 1, 720)
    if mins:
        core.log_session(uid(), mins, resource_id=rid)
    flash("Marked complete. Your skill progress is updated (an estimate, not an exam).", "ok")
    return redirect(url_for("learner.next_move"))


@bp.route("/log-session", methods=["POST"])
@login_required
def log_session():
    mins = _int(request.form.get("minutes"), 1, 720)
    if mins is None:
        flash("Enter minutes between 1 and 720.", "error")
    else:
        core.log_session(uid(), mins, request.form.get("topic", ""), _int(request.form.get("resource_id"), 1, 10 ** 6))
        flash(f"Logged {mins} minutes.", "ok")
    return redirect(request.referrer or url_for("learner.progress"))


@bp.route("/progress")
@login_required
def progress():
    snap = core.learning_snapshot(uid())
    days = core.daily_minutes(uid(), 14)
    skills = q("SELECT s.name, us.level FROM user_skills us JOIN skills s ON s.id=us.skill_id WHERE us.user_id=? ORDER BY us.level DESC", (uid(),))
    p = core.get_profile(uid())
    _, stages = core.roadmap_stages(uid(), p["career_id"] if p else None)
    done = [r for r in q("SELECT r.id, r.title, lp.completed_at FROM learning_progress lp JOIN resources r ON r.id=lp.resource_id "
                         "WHERE lp.user_id=? AND lp.status='completed' ORDER BY lp.completed_at DESC LIMIT 10", (uid(),))]
    quiz = q("SELECT s.name, qa.score, qa.total, qa.created_at FROM quiz_attempts qa JOIN skills s ON s.id=qa.skill_id "
             "WHERE qa.user_id=? ORDER BY qa.created_at DESC LIMIT 5", (uid(),))
    projects = q("SELECT p.id, p.title, up.status FROM user_projects up JOIN projects p ON p.id=up.project_id WHERE up.user_id=?", (uid(),))
    return render_template("progress.html", snap=snap, days=days, skills=skills, stages=stages, done=done, quiz=quiz,
                           projects=projects, maxm=max([m for _, m in days] + [30]), level_label=core.level_label,
                           demo=bool(g.user["is_demo"]))


# ------------------------------------------------------------ feedback & reviews
@bp.route("/resources/<int:rid>/feedback", methods=["POST"])
@login_required
def rec_feedback(rid):
    if not q1("SELECT 1 FROM resources WHERE id=?", (rid,)):
        abort(404)
    useful = 1 if request.form.get("useful") == "1" else 0
    reason = request.form.get("reason", "")
    if reason not in core.FEEDBACK_REASONS:
        reason = ""
    run("INSERT INTO recommendation_feedback(user_id, resource_id, useful, reason) VALUES (?,?,?,?)", (uid(), rid, useful, reason))
    msg = "Thanks - we'll weigh that in." if useful else "Got it - we'll adjust your future recommendations."
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify(ok=True, message=msg)
    flash(msg, "ok")
    return redirect(request.referrer or url_for("learner.dashboard"))


@bp.route("/resources/<int:rid>/review", methods=["POST"])
@login_required
def review(rid):
    if not q1("SELECT 1 FROM resources WHERE id=?", (rid,)):
        abort(404)
    rating = _int(request.form.get("rating"), 1, 5)
    diff = request.form.get("difficulty_feedback", "")
    if rating is None:
        flash("Choose a rating from 1 to 5.", "error")
    else:
        run("INSERT INTO resource_reviews(user_id, resource_id, rating, difficulty_feedback, review) VALUES (?,?,?,?,?) "
            "ON CONFLICT(user_id, resource_id) DO UPDATE SET rating=excluded.rating, difficulty_feedback=excluded.difficulty_feedback, "
            "review=excluded.review, created_at=datetime('now')",
            (uid(), rid, rating, diff if diff in ("too_easy", "just_right", "too_hard") else "", request.form.get("review", "").strip()[:600]))
        flash("Your review was saved. It is shown separately from external ratings.", "ok")
    return redirect(url_for("main.resource_detail", rid=rid))


# ------------------------------------------------------------ projects
@bp.route("/projects")
@login_required
def projects():
    levels = core.user_skill_levels(uid())
    gap = {g_["skill_id"] for g_ in core.skill_gap(uid()) if g_["gap"] > 0}
    rows = []
    for p in q("SELECT * FROM projects ORDER BY difficulty, title"):
        sk = q("SELECT s.id, s.name FROM skills s JOIN project_skills ps ON ps.skill_id=s.id WHERE ps.project_id=?", (p["id"],))
        up = q1("SELECT status FROM user_projects WHERE user_id=? AND project_id=?", (uid(), p["id"]))
        avg = sum(levels.get(s["id"], 0) for s in sk) / len(sk) if sk else 0
        rows.append({"p": p, "skills": sk, "status": up["status"] if up else None,
                     "fit": p["difficulty"] == core_diff(avg), "relevant": any(s["id"] in gap for s in sk)})
    rows.sort(key=lambda r: (not r["fit"], not r["relevant"], r["p"]["difficulty"]))
    return render_template("projects.html", rows=rows, diff=core.DIFF)


def core_diff(avg):
    return 1 if avg < 35 else 2 if avg < 70 else 3


@bp.route("/projects/<int:pid>")
def project_detail(pid):
    p = q1("SELECT * FROM projects WHERE id=?", (pid,))
    if not p:
        abort(404)
    sk = q("SELECT s.* FROM skills s JOIN project_skills ps ON ps.skill_id=s.id WHERE ps.project_id=?", (pid,))
    up = q1("SELECT * FROM user_projects WHERE user_id=? AND project_id=?", (uid(), pid)) if g.user else None
    return render_template("project.html", p=p, skills=sk, up=up, diff=core.DIFF)


@bp.route("/projects/<int:pid>/status", methods=["POST"])
@login_required
def project_status(pid):
    if not q1("SELECT 1 FROM projects WHERE id=?", (pid,)):
        abort(404)
    status = request.form.get("status")
    if status not in ("started", "completed"):
        abort(400)
    repo = request.form.get("repo_url", "").strip()[:200]
    if repo and not repo.startswith(("http://", "https://")):
        flash("Repository link must start with http:// or https://", "error")
        return redirect(url_for("learner.project_detail", pid=pid))
    run("INSERT INTO user_projects(user_id, project_id, status, repo_url) VALUES (?,?,?,?) "
        "ON CONFLICT(user_id, project_id) DO UPDATE SET status=excluded.status, repo_url=excluded.repo_url, updated_at=datetime('now')",
        (uid(), pid, status, repo))
    if status == "completed":
        for s in q("SELECT skill_id FROM project_skills WHERE project_id=?", (pid,)):
            run("INSERT INTO user_skills VALUES (?,?,15) ON CONFLICT(user_id, skill_id) DO UPDATE SET level=MIN(100, level+15)", (uid(), s["skill_id"]))
        core.notify(uid(), "Project completed - add it to your portfolio.", "milestone")
    flash("Project updated.", "ok")
    return redirect(url_for("learner.project_detail", pid=pid))


# ------------------------------------------------------------ bookmarks
@bp.route("/bookmarks", methods=["GET"])
@login_required
def bookmarks():
    rows = []
    for b in q("SELECT * FROM bookmarks WHERE user_id=? ORDER BY created_at DESC", (uid(),)):
        t = {"resource": ("SELECT id, title, provider FROM resources WHERE id=?", "/resources/"),
             "project": ("SELECT id, title, '' provider FROM projects WHERE id=?", "/projects/"),
             "roadmap": ("SELECT c.id id, r.title title, '' provider FROM roadmaps r JOIN careers c ON c.id=r.career_id WHERE r.id=?", "/careers/")}[b["kind"]]
        item = q1(t[0], (b["ref_id"],))
        if item:
            link = t[1] + (q1("SELECT slug FROM careers WHERE id=?", (item["id"],))["slug"] if b["kind"] == "roadmap" else str(item["id"]))
            rows.append({"b": b, "item": item, "link": link})
    return render_template("bookmarks.html", rows=rows, folders=core.FOLDERS)


@bp.route("/bookmarks/toggle", methods=["POST"])
@login_required
def bookmark_toggle():
    kind = request.form.get("kind")
    ref = _int(request.form.get("ref_id"), 1, 10 ** 9)
    folder = request.form.get("folder", "Learn Later")
    if kind not in ("resource", "project", "roadmap") or ref is None or folder not in core.FOLDERS:
        abort(400)
    ex = q1("SELECT id FROM bookmarks WHERE user_id=? AND kind=? AND ref_id=?", (uid(), kind, ref))
    if ex and not request.form.get("move"):
        run("DELETE FROM bookmarks WHERE id=?", (ex["id"],))
        msg = "Removed from saved."
    elif ex:
        run("UPDATE bookmarks SET folder=? WHERE id=?", (folder, ex["id"]))
        msg = f"Moved to {folder}."
    else:
        run("INSERT INTO bookmarks(user_id, kind, ref_id, folder) VALUES (?,?,?,?)", (uid(), kind, ref, folder))
        msg = f"Saved to {folder}."
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify(ok=True, message=msg)
    flash(msg, "ok")
    return redirect(request.referrer or url_for("learner.bookmarks"))


# ------------------------------------------------------------ mentor
@bp.route("/mentor")
@login_required
def mentor_page():
    return render_template("mentor.html", modes=mentor.MODES, ai_enabled=bool(current_app.config.get("LLM_API_KEY")))


# ------------------------------------------------------------ quiz
@bp.route("/quiz/<int:sid>", methods=["GET", "POST"])
@login_required
def quiz(sid):
    skill = q1("SELECT * FROM skills WHERE id=?", (sid,))
    if not skill:
        abort(404)
    qs = q("SELECT * FROM quiz_questions WHERE skill_id=? ORDER BY id", (sid,))
    if not qs:
        return render_template("quiz.html", skill=skill, qs=[], result=None)
    if request.method == "POST":
        score, detail = 0, []
        for item in qs:
            pick = request.form.get(f"q{item['id']}", "")
            ok = pick == item["answer"]
            score += ok
            detail.append({"q": item, "pick": pick, "ok": ok})
        run("INSERT INTO quiz_attempts(user_id, skill_id, score, total) VALUES (?,?,?,?)", (uid(), sid, score, len(qs)))
        # a quiz can only nudge the estimate upward to the score-implied level, never invent mastery
        pct = round(100 * score / len(qs))
        run("INSERT INTO user_skills VALUES (?,?,?) ON CONFLICT(user_id, skill_id) DO UPDATE SET level=MAX(level, ?)",
            (uid(), sid, min(pct, 80), min(pct, 80)))
        return render_template("quiz.html", skill=skill, qs=qs, result={"score": score, "total": len(qs), "detail": detail})
    return render_template("quiz.html", skill=skill, qs=qs, result=None)


# ------------------------------------------------------------ semester & exam
@bp.route("/semester", methods=["GET", "POST"])
@login_required
def semester():
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:80]
        exam = request.form.get("exam_date", "")
        try:
            if exam:
                datetime.strptime(exam, "%Y-%m-%d")
        except ValueError:
            exam = None
            flash("Exam date must be a valid date.", "error")
        tm = _int(request.form.get("target_marks"), 0, 100)
        hrs = _int(request.form.get("hours_per_week"), 0, 80, 4)
        if not name:
            flash("Enter a subject name.", "error")
        elif exam is not None:
            cur = run("INSERT INTO semester_subjects(user_id, name, exam_date, is_weak, target_marks, hours_per_week) VALUES (?,?,?,?,?,?)",
                      (uid(), name, exam or None, 1 if request.form.get("is_weak") else 0, tm, hrs))
            for t in request.form.get("topics", "").replace(";", "\n").splitlines()[:40]:
                if t.strip():
                    run("INSERT INTO syllabus_topics(subject_id, topic) VALUES (?,?)", (cur.lastrowid, t.strip()[:100]))
            flash("Subject added.", "ok")
        return redirect(url_for("learner.semester"))
    subs = []
    total_h = 0
    for s in q("SELECT * FROM semester_subjects WHERE user_id=? ORDER BY exam_date IS NULL, exam_date", (uid(),)):
        topics = q("SELECT * FROM syllabus_topics WHERE subject_id=? ORDER BY id", (s["id"],))
        days = (datetime.strptime(s["exam_date"], "%Y-%m-%d").date() - date.today()).days if s["exam_date"] else None
        done = sum(1 for t in topics if t["done"])
        subs.append({"s": s, "topics": topics, "days": days, "done": done})
        total_h += s["hours_per_week"]
    p = core.get_profile(uid())
    career_h = max(0, round((p["minutes_per_day"] * 7) / 60 - total_h, 1)) if p else 0
    return render_template("semester.html", subs=subs, academic_h=total_h, career_h=career_h, p=p)


@bp.route("/semester/<int:sid>/delete", methods=["POST"])
@login_required
def semester_delete(sid):
    run("DELETE FROM semester_subjects WHERE id=? AND user_id=?", (sid, uid()))
    return redirect(url_for("learner.semester"))


@bp.route("/topics/<int:tid>/toggle", methods=["POST"])
@login_required
def topic_toggle(tid):
    t = q1("SELECT t.* FROM syllabus_topics t JOIN semester_subjects s ON s.id=t.subject_id WHERE t.id=? AND s.user_id=?", (tid, uid()))
    if not t:
        abort(404)
    field = "is_weak" if request.form.get("field") == "weak" else "done"
    run(f"UPDATE syllabus_topics SET {field}=1-{field} WHERE id=?", (tid,))     # field is one of two literals above
    return redirect(request.referrer or url_for("learner.semester"))


@bp.route("/exam")
@login_required
def exam():
    last_minute = request.args.get("mode") == "last-minute"
    plan, today = [], date.today()
    for s in q("SELECT * FROM semester_subjects WHERE user_id=? AND exam_date IS NOT NULL ORDER BY exam_date", (uid(),)):
        days = (datetime.strptime(s["exam_date"], "%Y-%m-%d").date() - today).days
        if days < 0:
            continue
        topics = q("SELECT * FROM syllabus_topics WHERE subject_id=? AND done=0 ORDER BY is_weak DESC, id", (s["id"],))
        total = scalar("SELECT COUNT(*) FROM syllabus_topics WHERE subject_id=?", (s["id"],))
        # weak topics first, then the rest; spread evenly across the days left (min 1/day), last 2 days = revision only
        study_days = max(1, days - 2)
        per_day = max(1, -(-len(topics) // study_days)) if topics else 0
        sched = []
        for d in range(min(study_days, 14)):
            chunk = topics[d * per_day:(d + 1) * per_day]
            if chunk:
                sched.append((today + timedelta(days=d), [t["topic"] for t in chunk]))
        plan.append({"s": s, "days": days, "topics": topics, "total": total, "sched": sched,
                     "weak": [t for t in topics if t["is_weak"] or s["is_weak"]][:5]})
    quizzes = q("SELECT DISTINCT s.id, s.name FROM skills s JOIN quiz_questions qq ON qq.skill_id=s.id ORDER BY s.name")
    return render_template("exam.html", plan=plan, last_minute=last_minute, quizzes=quizzes)


# ------------------------------------------------------------ readiness & notifications
@bp.route("/readiness", methods=["GET", "POST"])
@login_required
def readiness():
    if request.method == "POST":
        key = request.form.get("item")
        if key in core.READINESS_ITEMS:
            run("INSERT INTO readiness_items VALUES (?,?,?) ON CONFLICT(user_id, item) DO UPDATE SET done=1-done", (uid(), key, 1))
        return redirect(url_for("learner.readiness"))
    items, pct = core.readiness(uid())
    return render_template("readiness.html", items=items, pct=pct)


@bp.route("/notifications", methods=["GET", "POST"])
@login_required
def notifications():
    if request.method == "POST":
        run("UPDATE notifications SET is_read=1 WHERE user_id=?", (uid(),))
        return redirect(url_for("learner.notifications"))
    rows = q("SELECT * FROM notifications WHERE user_id=? ORDER BY created_at DESC, id DESC LIMIT 50", (uid(),))
    return render_template("notifications.html", rows=rows)
