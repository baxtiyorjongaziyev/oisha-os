# Automatic script learning

The existing audio/transcription pipeline captures private seller utterances from
sales calls with quality score >=75, a known conversation family/service, and a
source recording timestamp. A model's payment/meeting/proposal claim is not proof
of a completed sale. Reconciliation checks amoCRM lead identity, won status 142,
and closed_at >= recording time. CRM won does not establish payment receipt or
that a particular phrase caused the sale.

At least three distinct won leads per conversation family/service are required.
One highest-quality call per lead contributes; top ten samples form the version.
Only attributed seller text is extracted. Phone/email/URL patterns are masked;
sensitive-labelled utterances are excluded. Other names/details may remain, so
this is a private coaching library, not public/anonymized training data.

`data/winning_sales_scripts.sqlite3` stores candidates, verification state and
append-only script versions transactionally. It is gitignored. The previous JSON
library is not imported: its conversion claims/keyword-derived techniques are not
sufficient evidence. No customer phone or manager name is copied into samples.

The existing call scan captures samples in both direct and approval flows. It
rechecks up to twenty candidate leads, at most hourly per lead. Reopened/lost
leads cease to qualify; evidence older than 24 hours is excluded. Already analyzed
calls encountered by the scanner can be reclassified from their stored transcript
without rewriting CRM; this is limited to three per analyzer/sweep, idempotent and
hourly retryable on model failure. Unknown recording times and untyped calls are
not guessed. This is bounded scanner coverage, not a claim of full historical audit.

`SalesQualityCoach.generate_ideal_script()` reads current versions, including
source call/lead IDs. Existing weekly owner delivery can use that output. No new
message is sent by learning hooks. Official playbook weights and payroll/KPI rules
remain outside the learner. Better conversion requires a later controlled outcome
comparison; adding a version alone is not evidence of uplift.

Local implementation validation: synthetic cases cover delayed wins, repeated calls,
separate types/services, post-sale recordings, CRM outages/reopened deals, stale
evidence, persistence, concurrent capture, historical replay and coach consumption.
Deployment and live acceptance are separate steps.
