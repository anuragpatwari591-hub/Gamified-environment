# Future AI integration

## What exists now

* **Explainable recommender** - the real intelligence of v1 (see recommendation-engine.md). Not machine learning, and not presented as such.
* **AI Study Mentor** with an adapter boundary in `app/services/mentor.py`:

```
reply(uid, mode, message)
  -> fallback(...)            # always computed first (rules + database)
  -> get_adapter()            # LLMAdapter (no-op) unless LLM_API_KEY and LLM_MODEL are set
  -> adapter.complete(system, user)   # only for 'explain' and 'career' modes
  -> on ANY exception: keep the fallback answer and add a note
```

`HTTPAdapter` is written for the Anthropic Messages API shape (`x-api-key`, `anthropic-version`, `messages`). It is **untested against a live key**; the failure path is covered by `test_mentor_falls_back_when_llm_fails`. The model name is read from `LLM_MODEL`; nothing is hard-coded. The profile line sent as context contains stream, year, goal, level, study time and language - no name or email.

## Turning it on

```
LLM_API_KEY=...   LLM_MODEL=<model id from your provider>
```
Update the privacy policy (mentor questions then leave the server), and add per-user usage limits.

## Natural next steps

1. LLM-written explanations that cite the user's roadmap stage, with the deterministic answer as a guard-rail.
2. Retrieval over the resource catalogue so the model recommends only listed resources.
3. Learned ranking: replace hand-set weights with weights fitted from `recommendation_feedback`, keeping the explanation layer.
4. Automatic resource discovery/refresh: scheduled link and metadata checks (extends `scripts/verify_links.py`), always with admin approval.
5. Verified skill assessments, mobile app, mentor marketplace, institutional dashboards - all out of scope for v1.
