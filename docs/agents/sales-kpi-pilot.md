# JonBranding KPI pilot — proposal, 2026-10-30

This is a simulation, not an approved compensation policy. There is no activation
endpoint, salary write, payment creation or automatic deduction.

## Proposed model

`total = min(actual / target * 100, 100) * .50 + discipline * .25 + quality * .25`

- Result: owner-entered actual and target in the same unit and period. Choose a
  finance-approved definition (collected revenue, net revenue or margin) before use.
- Discipline: on-time completed tasks / tasks due, capped at 100. Completed cannot
  exceed due. Zero due tasks means unavailable, not a perfect or zero score.
- Quality: mean score of at least 20 distinct sales calls with current human approval;
  a corrected ROP score replaces the AI score. Rejected, appealed, pending, non-sales,
  other managers and superseded snapshots are excluded. Counts and means by call
  type are returned for inspection. The 20-call minimum and 50/25/25 weights are
  starting proposals, not validated benchmarks or owner-approved decisions.

The period is the latest review timestamp, start-inclusive/end-exclusive, **not**
the date the call occurred. It must not be represented as a monthly call cohort.
Managers with different call-type mixes are not yet adjusted for case difficulty.
Approved means human-approved; it does not prove an independent blinded ROP grade.

Missing components prevent a total and bonus preview. Weights never silently
renormalize and unknown values never become zero. An optional bonus pool produces
a preview only, rounded half-up to two decimal places (UZS or USD). No cap over
100% and no overperformance accelerator are proposed in this version.

## Access and provenance

The conversation intelligence panel shows the simulator to reviewers. The API
requires both all-call and finance read permissions; simulation additionally
requires owner/admin. Client-supplied quality values and unknown input fields are
rejected. Quality comes from current stored reviews scoped to manager and window,
without the general evaluation list's 500-row truncation.

Financial and task inputs are manual simulation values, not verified ledger/CRM
facts. Requests are not saved by this feature. No secret values are needed.

## Before any compensation impact

Owner must approve result definition, task rules, weights, minimum sample, period,
bonus pool, appeal procedure and who can review. Implement verified finance/task
sources and a call-date cohort; run shadow calculations over a full sales cycle.
Compare independent AI/ROP grades on representative call types and languages,
measure error and bias, and agree acceptance thresholds before enabling anything.
Version and freeze each period, handle appeals/reversals, audit access and require
an explicit owner-approved activation change. A high AI score or CRM won status
alone is not verified payment or a basis for automatic salary changes.
