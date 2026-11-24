# Registrar workflows

The registrar workspace supports applications, admissions conversion, registration, waitlists, official grades, degree audits and credential issuance. Public applicants verify their email before submitting applications. Follow ADMISSION_LIFECYCLE.md for decisions and conversion; TRANSCRIPTS.md and ADVISING_DIPLOMAS.md describe credential snapshots.

## Registration and withdrawal

Published courses use registration windows, capacity limits, holds and prerequisite rules. PostgreSQL locks serialize capacity changes; direct administrator enrollment edits bypass that workflow and must be restricted. Existing final grades and approved transfer credits satisfy prior-completion rules. Named prerequisite groups offer alternatives; all groups must pass. Corequisites accept an active enrollment in the same term or qualifying prior credit. Minimum grade points can be required. Mutual corequisites do not yet have a simultaneous registration cart.

Withdrawal deadlines are independent of registration. Configure a WithdrawalWindow for each eligible course. Students submit a reason from their academic record. Authorized registrars review the withdrawal queue. Approval deactivates the enrollment, records a released W with no credits or GPA points and considers waitlist promotion within the registration period. A released final grade blocks withdrawal approval. Approved withdrawals cannot be silently reactivated by student registration. Denied requests are retained; appeals and corrections require registrar handling.

## Grading and standing

An active program grading scale requires an institutional approval reference. Enter unique thresholds including zero, letter labels, GPA points and passing flags. The Final grades workspace creates a draft from an entered percentage and the configured scale; a separate release action validates it before student visibility. Existing grades require the established controlled correction process; this screen does not overwrite them. Generic grade administration remains privileged and must be supervised. W and I cannot award credits or GPA points.

Standing policies are disabled by default. After institutional approval, configure the minimum cumulative GPA and approval reference. Calculate standing for a student and term using released GPA grades from terms ending on or before the selected term. Each calculation preserves a new policy/GPA snapshot. Prior results remain unchanged when policy changes. No automatic dismissal, hold or student-status change occurs. Repeat-course replacement and appeal policies still need institutional requirements and implementation.

## Student records

Students manage up to three emergency contacts, download their portal-visible records as JSON, view standing history and issue a private enrollment-verification PDF. The export expressly excludes attachments, internal notes and audit logs; it is not a complete reviewed records request. Enrollment letters preserve the active-enrollment snapshot at issuance and are not digitally signed. Student status changes made through model saves record previous/current status; existing historical transitions cannot be reconstructed, and bulk database updates bypass signals.

Regression coverage: academics.test_student_records exercises withdrawal approval/denial boundaries, no released-grade overwrite, custom grading, immutable standing history, prerequisite alternatives/corequisites and private exports/letters. Production institutional policy acceptance remains outstanding.
