# Changes

## Unreleased

- Add a bounded synthetic HTTP load workflow with disposable PostgreSQL/Redis/Gunicorn, authenticated concurrency ramps and latency/error artifacts.

- Add disabled-by-default document-retention policies, bounded previews, independent erasure review and preservation holds; retain version metadata and exclude erased payloads from downloads/exports.
- Fix the personal-file streaming regression test to avoid a duplicate response close that invalidated PostgreSQL test transactions.

- Add bounded private file archives with safe paths, digest manifests, current-access checks and revoked-credential exclusion.

- Add all-or-nothing multi-course registration for mutual corequisites with ordered capacity locks, preserved waitlist priority and repeat-safe enrollment notices.

- Batch dashboard/course related-record queries, reuse per-module access decisions within a request, and omit attachment binary payloads from course-page queries.

- Add disabled-by-default, policy-gated withdrawal appeals with independent reasoned decisions, preserved original denial snapshots and replay-safe W posting.

- Document current HTTP/data-exchange interfaces and add a synthetic role-based training and acceptance workbook.

- Correct obsolete registration, integration and scanner documentation; add troubleshooting and upgrade acceptance procedures with explicit external blockers.

- Share portal and scheduled academic-risk checks with current assignment/role eligibility, atomic notification queuing and repeat-safe counts-only summaries.

- Apply current approved course accommodations to new exam sessions with bounded, non-stacking extra time/attempts and private decision snapshots.
- Preserve granted active sessions after revocation while enforcing closing dates and blocking unapproved new attempts.

- Extend course JSON to version 2 with draft announcements/calendar events and closed instructor discussion prompts; retain version 1 import support.
- Share import/copy validation, shift offset-aware dates and reject nonempty communication targets without partial writes.
- Fix Gunicorn root logger configuration after production-stack CI exposed an inherited missing handler; add installed-default configuration regression coverage.

- Add private operational metrics, staff health workspace and transition-only failure/recovery notices.
- Scrub production application and access logs of arbitrary request/exception data.
- Add managed encrypted-backup manifests, failure status and restore-gated retention; avoid same-second backup overwrites.

- Add immutable institutional policy versions, independent approval, effective dates, withdrawal and per-version acknowledgments.
- Add disabled-by-default voluntary demographic collection tied to reviewed question choices and explicit consent.
- Add restricted aggregate counts, whole-question small-cell suppression and student withdrawal of current answers.

- Add campus classifications and carry applicant campus into student conversion.
- Add scoped dean/president dashboards and bounded private aggregate reports.
- Capture immutable reporting evidence with independent review, digest validation and approved snapshot exports.

- Add scholarship funds, private applications, reviewed eligibility snapshots and renewals.
- Reserve award budgets atomically and post/cancel/reverse institutional account credits without overwriting financial history.

- Add append-only confirmed manual-payment refunds, withheld-funds disputes and once-only recovery postings.
- Release affected invoice allocations without rewriting their history; show net payments on receipts and reconciliation exports.
- Add disabled-by-default approved financial registration holds with installment/grace handling, independent manual holds and audited transitions.

- Finalize immutable transcript/diploma PDF artifacts with optional required digital signing and fail-closed issuance.
- Add private credential downloads, privacy-limited public verification/file comparison, revocation and replay-safe replacement.
- Add approved text templates and cryptographic signature/tamper tests with ephemeral certificates; institutional signing acceptance remains outstanding.

- Add private preview-and-commit bulk student/course imports with atomic rollback and replay protection.
- Add institutional branding settings, contrast-validated colors and scanned/re-encoded logo uploads.
- Add per-user timezone and dashboard preferences and scoped search filters. New official record snapshots capture the configured institution name.

- Add assigned-advisor appointments, support cases, shared/private notes, success-plan snapshots, intervention tracking and standing alerts.
- Add dated functional accommodation drafting, approval, revocation and scoped instructor/student visibility.
- Fix PostgreSQL activation recovery by locking the account without nullable joins.

- Add admissions reviewer assignments, private notes, conflict-checked interviews, document verification and conversion export.
- Add marker-bound activation recovery with token rotation and no reactivation of disabled student accounts.
- Add private student/admissions/institutional document libraries, multiple coursework files, retained versions and shared upload quotas.
- Pin encrypted recovery CI to Ubuntu 24.04 after the latest runner lacked the PostgreSQL 16 package.

- Add five browser configurations, sampled automated accessibility checks and guarded synthetic demonstration data.
- Fix keyboard skip-navigation interference from login autofocus and WebKit skip-link focus.
- Add real ClamAV clean/EICAR/outage checks and an encrypted PostgreSQL recovery drill with exact application-data comparison.

- Add independent withdrawal windows and reviewed W-grade processing, grading scales, standing snapshots, emergency contacts, personal exports and private enrollment letters.
- Add grouped prerequisites, grade thresholds, corequisites and student-status history.
- Correct obsolete registrar documentation and validate grade release.

- Add institutional AI approval/configuration, role-filtered approved knowledge documents, atomic budget reservations, usage analytics and anomaly shutdown.
- Preserve no prompt/answer history; retain conservative charges when provider billing is unknown.

- Add revocable account sessions, audited administrative lock/unlock/revoke actions and failed-login controls.
- Add durable private notifications, email preferences, retry history and event notices for admissions, enrollment, grades, payments and security.
- Add security incident administration, response procedures, dependency/static scans and production stack/restore smoke workflows.
- Fix an intermittent activation test to follow the token actually sent in email.

- Add lesson completion, prerequisite modules, HTTPS video links, scoped attendance participation and policy-gated private course certificates.
- Add validated versioned JSON course packages with atomic import and no student records.

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
