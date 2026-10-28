# Business model

**Actual revenue today: INR 0.** No affiliate partners, sponsors, customers or institutions exist. Everything below is *potential*. The product only contains the plumbing to measure and disclose such revenue honestly.

| Stream | Status in the code | Potential (not actual) |
|---|---|---|
| Affiliate commissions | Per-resource `affiliate_url`/`affiliate_ref`; every outbound click is logged; conversions and commission are entered **manually** by an admin from a partner report; disclosure on resource pages | Commission when a student buys a paid course through a link. Depends on partner programmes (not signed up) |
| Sponsored placements | `sponsored_content` table, "Sponsored" label, separate box, excluded from scoring. One placeholder marked **Demo Data** | Companies pay to feature a track or course, always labelled |
| Premium student features | *Coming Soon* - nothing implemented | Portfolio review, mentor matching, advanced analytics, personalised study planning |
| Institutional partnerships / B2B dashboards | *Coming Soon* | Colleges/coaching institutes get cohort dashboards (would need aggregated, consented data) |
| Recruitment partnerships | *Coming Soon* | Employers sponsor skill tracks or browse consented portfolios |

## Trust rules that protect the model

1. Revenue never enters `score_resource` (unit-tested).
2. Free-first is the default; paid courses always show free alternatives where they exist.
3. Sponsored content is visually separate and labelled; affiliate links are disclosed on the page and in `/disclosure`.
4. Admin analytics only show recorded events; potential revenue is not displayed as revenue.
5. No fake ratings, reviews, testimonials, salary figures or student counts.

## Costs to consider (not estimated here)

Hosting, domain, content curation time, optional LLM API usage, legal review. No figures are given because none have been measured.
