# YouTrack [QA] Subtask — Body Template

> Template for the body content of a `[QA] [<module>] <parent-summary>` subtask in YouTrack.
> Used in `qa_workflow.md` Phase 1.5. Strict English, dry, engineering register.
> Length budget: **15-30 lines** total. Brevity is a feature.

---

## Required structure (5 sections)

```markdown
## Scope
<1-2 lines: what's covered, what's explicitly out of scope>

## Approach
<2-4 lines: layers tested (UI / API / DB) + tools/scripts used>

## Risks
<2-4 lines: top 2-3 risk areas, with TRD references to past bugs in this domain
 — link to bugs.json findings, defect-clustering signals>

## AC coverage
<2-4 lines: gaps (AC point not covered by any case), conflicts (case contradicts AC),
 questions to PO if ambiguity surfaces>

## Environment + roles
<1-2 lines: env(s) used (stage / release / both), roles tested
 (Agent / Admin / Super Admin / qatestbot)>
```

---

## Style rules

| Rule | Why |
|---|---|
| **English only.** | Team artefact, dev/PO may not be Russian-readers (per `qa_persona.md §7`). |
| **No first person.** «Tested via Playwright», not «I tested via Playwright». | Engineering register. |
| **No hedging.** Не пиши «probably», «maybe», «I think». | Facts only. |
| **No emoji** unless part of the parent's section convention (e.g. `📌 Prerequisites` if mirroring bug template — but normally no emoji). | Clean visual. |
| **Lists for risks / gaps**, prose for scope/approach. | Scannable. |
| **Cite TRD-IDs** when referencing past bugs or related stories. | Traceability. |
| **No duplication of AC** — assume reader has parent ticket open. | Brevity. |

---

## Worked example — TRD-11639 case

Parent: `[Email builder] Improve Dashboard / Drilldown for sent emails statistics`
QA subtask title: `[QA] [Email builder] Improve Dashboard / Drilldown for sent emails statistics`

```markdown
## Scope
Verification of Sent emails counter on Dashboard (Conversion + Retention) and Drilldown reports
on stage and release. Out of scope: System emails (covered by separate flow), email template
authoring.

## Approach
- UI: Playwright drives Dashboard + Drilldown grids; capture network for /command/process and
  /api/dashboard/conversion endpoints.
- API: direct Postman POST to Send / Bulk endpoints for counter increment validation.
- DB: SQL on `client_emails` (`status`, `created_by_agent_id`, `email_templates_components_id`)
  to verify scope filter logic per Insight 12.

## Risks
- `created_by_agent_id` NULL on agent-driven sends → counter does not increment (TRD-11639 root
  cause confirmed by Vladislav Zhelihovsky 2026-04-29). Defect-clustering: check Bulk send same
  pattern (TRD-13752 already filed).
- Stage/release schema drift on email tables — release lacks `email_templates`/`client_emails`
  (Insight 14, db_diff__stage_vs_release.md). Counter behavior on release uses legacy
  `mail_templates` flow only.
- 2FA layer interaction with sensitive-column exports (Insight 5) when email is in report scope.

## AC coverage
- AC #1 (Bulk send creates one client_emails record per client): covered by Allure case 12544 +
  TRD-13752 negative reproduction.
- AC #3 (counter mirrors actual sent emails): covered, but stage-only — release not testable
  due to schema drift.
- Gap: AC #5 (lang priority on bulk) — implementation unclear, raised as open question to PO.

## Environment + roles
Stage (primary, full coverage). Release (partial — old email schema only). Roles: Agent
(qatestbot), Admin (yaroslavqa), Super Admin (aaa).
```

Total: 24 lines. Within budget.

---

## Anti-patterns (don't do)

- ❌ Body that just says «Testing task for TRD-XXXXX» — that's the OLD pattern, not the target.
- ❌ Copy-paste of full `test_prep/<TRD>/<TRD>.md` — that's the local artefact, this is the
  abridged public version. Different lengths, different audiences.
- ❌ Promises («will test thoroughly») — describe approach as currently planned, not future
  intent. If the plan changes, edit the subtask.
- ❌ Status updates inside the body («tested 2026-05-04 — OK») — use comments for those.
- ❌ Russian language anywhere in the body or title.

---

## Maintenance

When YouTrack workflow changes (new custom field, new state machine, etc.), update this
template + the corresponding section in `qa_workflow.md` Phase 1.5. Keep both in sync.

Sourced from: TRD-12170 reference example + Yaroslav's stated convention 2026-05-05.
