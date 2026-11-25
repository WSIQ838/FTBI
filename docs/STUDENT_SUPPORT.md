# Advising and student support

Students and assigned advisors use the Student support workspace. Advisors offer future appointment slots up to four hours long. Students book available times from their active advisor assignments; active student status is required. The service prevents double booking and overlapping student appointments. Students may cancel before the appointment starts. Advisors can cancel, mark a past appointment completed, or close a slot and cancel its booking. Scheduling notices are private and queued; external calendars are not integrated.

Students open support cases for assigned advisors, and advisors can open cases from their caseload. Cases track open, in-progress and resolved status. Students can add shared notes. Advisors can add shared or private notes; private notes and interventions never appear in the student view. Access is removed when the advisor assignment becomes inactive. There is no broad support-case administration bypass. Reassignment and escalation to other departments remain future work.

Advisors record success plans with goals, actions and review dates. Each save adds a new snapshot; earlier plans remain visible to the student and advisor. Private interventions record an action, follow-up date and outcome. A completion action records the final outcome once. Case and intervention changes are audited.

The academic-standing review action creates deduplicated advisor alerts for each student's latest recorded probation standing. It relies on the institution-approved standing policy used to calculate that record; it does not predict risk or change registration holds, student status or grades. Alerts can be acknowledged and remain in the history. Automated scheduled generation, richer signals and institutional intervention protocols remain outstanding.

## Accommodations

The Accommodation Administration role can draft, approve and revoke dated functional adjustments for active course enrollments. Records require an approval reference and should contain only the adjustments staff must implement, never diagnoses or medical evidence. Students see their own records. Course instructors see only approved, current records for actively enrolled students. Unrelated instructors cannot view them. Revocation removes instructor visibility immediately.

General accommodation records do not automatically change examination timing. Authorized examination staff must separately configure the existing per-quiz ExamAccommodation. Institutional eligibility decisions, approved wording, retention and privacy review remain external acceptance requirements.

Tests cover scheduling and privacy, case creation and resolution, assignment revocation, private notes, immutable success-plan snapshots, intervention completion, deduplicated alerts and accommodation lifecycle. PostgreSQL CI separately checks concurrent booking of a single slot.
