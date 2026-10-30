# JonBranding KPI pilot — proposal, 2026-10-30

This is a simulation, not an approved compensation policy. There is no activation
endpoint, salary write, payment creation or automatic deduction.

## Owner daily funnel targets (2026-10-30)

50 distinct answering customers, with at least 180 seconds of conversation each,
then 20 meaningful conversations, 10 EVQN meeting invitations, 3 actually attended
online/offline meetings and 1 sale. Repeat attempts are not additional customers;
invitations are not attended meetings. The 50-customer minimum implies at least
150 minutes of conversation. At an assumed 50% answer rate, 100 attempts is a
planning estimate, not the KPI target and not a guaranteed sufficient count.

The API and panel expose these owner-stated targets, not measured counters.
The contextual AI pass now requests separate meaningful/EVQN evidence and validates
exact transcript quotations. Results are evidence candidates requiring human review;
they do not create daily CRM counts, invitations, KPI credit or payroll effects.
EVQN was defined by the owner: need, timing, decision maker/process and price.
Price discussion is not budget approval or payment. Another decision maker does
not itself fail qualification when the decision process is clarified.

The adapted meaningful-conversation pilot requires customer-confirmed need,
service fit, and an agreed next step (which may be something other than a meeting).
This adapts Salesforce BANT qualification and Gong's discovery scorecards; it is
our design, not their universal definition. Unknown evidence stays unknown;
unsupported quotations are removed. AI attribution/semantics still need ROP review.
Sources checked 2026-10-30:
- https://www.salesforce.com/blog/sales/what-is-bant-lead-generation/
- https://help.gong.io/docs/all-about-scorecards

Sale confirmation, whether 180 seconds must be one call or cumulative, and
attribution window still need definition. Daily activities and later outcomes from the originating cohort
must be separate; a later meeting/sale must not become a same-day failure.
These targets do not approve the proposed 50/25/25 compensation weights below.

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
