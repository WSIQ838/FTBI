# Changes

## Unreleased

- Add invoices, tuition schedules, idempotent billing, atomic manual-payment verification, payment allocations, installment plans, private PDF receipts and reconciliation CSV.
- Support partial Stripe checkout and reuse pending sessions. Verify signed webhook replay and amount checks.
- Add PostgreSQL concurrency tests for last-seat registration and payment webhook replay.

- Add true/false, essay, short-answer, fill-in-the-blank and matching assessments, question weights, manual grading, random question pools and attempt aggregation.
- Add explicit result-release controls and lock assessment definitions after sessions start.
- Add PostgreSQL-only simultaneous-submission regression coverage.

- Preserve the complete development checklist and explicitly track release blockers.
- Add assignment rubrics, submission limits, late windows, graded resubmission policies and private version history with archived attachments.
- Preserve prior grades and work when a student resubmits; clear the current grade for review.
- Extend internal course copying to rubrics, submission policies, quizzes and grading weights. Copies exclude student records and keep quizzes unpublished.
- Add regression tests for rubric scoring, policy enforcement, version privacy and content copying.

This is not a stable release. Production, live-provider and institutional acceptance remain open.
