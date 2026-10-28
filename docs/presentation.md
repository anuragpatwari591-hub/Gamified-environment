# Presentation outline (14 slides)

1. **Title** - NAVORA: "Stop searching. Start knowing what to learn next." Team, guide, course.
2. **Problem** - Information overload; students lack order, reasons and career linkage. (One striking example, no invented statistics.)
3. **Existing systems & gap** - search/YouTube/marketplaces/roadmap sites: not personalised, unclear ranking, commercial bias.
4. **Proposed system** - Student -> Profile -> Goal -> Skill gap -> Roadmap -> Resources -> Projects -> Career readiness. Show the loop *Discover -> Understand -> Plan -> Learn -> Practice -> Build -> Measure -> Improve*.
5. **Objectives & scope** - what is in, what is "Coming Soon".
6. **Architecture** - diagram from docs/architecture.md; stack: Flask, SQLite, Jinja, plain JS.
7. **Database** - ER diagram; 34 tables; trust fields on resources.
8. **Recommendation engine** - formula, component table, live example with "Why this?".
9. **Live demo** - demo student: dashboard -> Your Next Move -> roadmap -> skill gap -> resource detail (Why, quality, free alternatives) -> feedback changes next recommendation -> mentor chat -> semester/exam -> admin analytics.
10. **Trust & monetisation** - no fabricated data, free-first, sponsored labelling, affiliate disclosure, potential vs actual revenue.
11. **Security** - hashing, CSRF, CSP, rate limit, parameterised SQL, role checks.
12. **Testing** - 84 automated tests, bugs found/fixed, manual responsive checks, link reachability script.
13. **Limitations & future scope** - honest list; LLM adapter, learned ranking, deployment.
14. **Q&A** - viva bank in docs/viva.md.

Screenshots to capture before presenting: landing, dashboard (desktop + mobile), Next Move, roadmap, resource detail, compare, admin analytics.
