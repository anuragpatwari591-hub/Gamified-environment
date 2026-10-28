# Recommendation engine

File: `app/recommendation/engine.py` - pure functions, no database. Weights: `app/recommendation/weights.json`.

## Formula

```
match_score = 100 * ( sum_i  w_i * c_i ) / ( sum_i  w_i )          c_i in [0, 1]
```

The score is a weighted average, so adding or removing a component never breaks the 0-100 scale. If a user has not enabled free-first, the `free_first_bonus` term is simply left out of both sums.

| Component `c_i` | How it is computed | Default weight |
|---|---|---|
| `career_relevance` | 0.6-1.0 if the resource's skills are on the target career's list and the user is still short (gap/60 raises it); 0.3 if already met; 0 if unrelated; 0.5 neutral when no career chosen | 22 |
| `skill_relevance` | 1.0 if it covers the *current roadmap stage's* skill; 0.35 if a later stage; else 0 | 18 |
| `prerequisite_fit` | 0.25 if roadmap stages *before* its skill are unfinished (adds a caveat), 1.0 otherwise | 10 |
| `learning_style` | 1.0 if resource format is among the user's preferred formats, 0.4 otherwise | 10 |
| `difficulty_fit` | 1 - |resource difficulty - target difficulty| / 2, where target comes from the user's level in that skill (<35 beginner, <70 intermediate, else advanced) | 12 |
| `language` | 1.0 match; 0.3 mismatch for non-English users; 0.5 for English users | 6 |
| `time_fit` | duration vs. one week of study time: <=1 week fits (1.0); longer decays with `ratio^-0.5`; unknown -> 0.5 | 6 |
| `quality` | see below | 10 |
| `freshness` | 1.0 if verified <=90 days ago, linearly down to 0.4 at 365 days, 0.3 if never verified | 3 |
| `budget_fit` | free=1; paid depends on budget (free 0, mostly-free 0.35, paid-ok 0.8, premium 1) | 4 |
| `interest_match` | interests found in title/topic/tags/category (2 hits = 1.0), 0.5 neutral | 6 |
| `free_first_bonus` | free 1.0, freemium 0.5, paid 0 - only when free-first is on | 12 |

Not an input, on purpose: whether a resource is sponsored, has an affiliate link, or its commission. A unit test (`test_sponsored_flag_does_not_affect_score`) enforces this.

## Quality score (generic, 0-100)

Blends **external rating** (only if present; shrunk when rating count is small), **source credibility** (official 1.0 ... community 0.6, configurable), **freshness**, and **NAVORA student reviews** (only if >=3). Weights: 40/35/15/10. *Missing signals are dropped and the remaining weights renormalised* - a missing rating is never invented, and the UI says "Rating unavailable".

## Explanations

Each component that fires appends a plain-language reason ("It matches your preference for video lessons."). Weak points add *caveats* ("Paid resource.", "Rating unavailable.", "Earlier roadmap stages are not finished yet..."). The UI shows the first four reasons and three caveats.

## Free-first and paid courses

* With free-first on, free resources get the bonus term.
* `rank()` attaches `free_alternatives` (up to 2 free resources sharing a skill) to every paid item, so a paid course is never shown without them.
* Paid items can still outrank free ones if a premium-budget user's profile fits them much better - the ranking never hides a paid option, but it is never promoted for revenue.

## Learning loop (feedback)

Every "Was this useful?" answer is stored in `recommendation_feedback`. At scoring time:

| Feedback | Effect |
|---|---|
| Same resource marked not useful | score x 0.1 |
| `too_difficult` | resources with same-or-higher difficulty on shared skills x (1 - 0.35) |
| `too_long` | resources at least as long x 0.65 (partial weight 0.6) |
| `boring` / `wrong_style` | same-format resources x (1 - 0.35 * 0.8) |
| `wrong_topic` / `not_relevant` | resources sharing skills x 0.65 |
| `already_knew` | the resource's skills are assumed >= 40% in the user's context |
| Marked useful | same format + shared skill: x 1.05 |

`feedback_penalty` (0.35) is configurable.

## "Your Next Move"

`next_move(ctx, stages, resources, projects_by_skill)`:
1. current stage = first stage not done (done = manually completed or skill level >= stage target);
2. candidate pool = resources tagged with that stage's skill; rank them with that skill as focus;
3. output: title, reason (stage position + current level + top reasons), minutes (resource duration capped by the daily study time), resource, alternatives, milestone as the outcome, and the follow-up (the stage's project, otherwise its milestone).
If every stage is done it returns a portfolio action pointing at Career Readiness.

## Skill levels (honest by design)

Levels are estimates from (a) self-rating, (b) completed resources (+10-15 depending on difficulty), (c) completed projects (+15), (d) quiz results (can only raise the level, capped at 80). They are shown as estimates, never as certifications.

## Tuning

Edit `weights.json` and restart. Tests (`tests/test_engine.py`) show how each weight changes ranking.
