# Synthetic user-training and acceptance workbook

Draft training material, not completed user acceptance. A training coordinator must provide an approved isolated environment, synthetic accounts and fictional records. Never reuse production credentials, student records, real card payments or live message recipients. This workbook contains no installation instructions. Use separate student, instructor, registrar, finance, admissions, advisor and security accounts; do not teach routine work through a superuser account.

For each exercise record the application commit, role, fictional case ID, expected/observed outcome, pass/fail, issue reference and reviewer. Keep screenshots free of secrets and real personal information. An automated CI result does not replace the participant's acceptance record.

| Role | Exercise | Expected evidence |
| --- | --- | --- |
| Student | Sign in, navigate by keyboard, open an enrolled course, submit work and read released feedback. Try another student's course and document link. | Own work remains visible; unrelated private content is denied; navigation and errors are understandable. |
| Faculty | Author an unpublished assessment, configure a pool/policy, grade an essay and release results. Copy a course into an empty target and inspect draft notices/events. | Scores remain withheld until released; copied content excludes student attempts/replies and remains in the documented draft state. |
| Registrar | Review a synthetic withdrawal inside the allowed window, release a configured final grade, inspect standing and issue an eligible synthetic credential. | Audit/history preserved; W has no GPA credit; released grades cannot be silently overwritten; credential permissions and verification behave as documented. |
| Finance | Create a fictional invoice, verify a synthetic manual payment, allocate it and record a confirmed simulated manual refund. | Original ledger/allocation history remains; net balance and invoice availability reconcile. This exercise does not establish Stripe or bank acceptance. |
| Admissions | Review an application, add a scoped note, schedule an interview, record a decision and review conversion. | Unauthorized applicants/staff cannot read notes; decisions and activation follow the approved workflow. Live email remains a separate gate. |
| Advisor | Book/cancel a slot, create shared and private case notes, record a success plan and review a standing alert. | Double booking denied, student sees shared material only, inactive caseload assignments lose access, repeated risk checks do not duplicate notices. |
| Accommodation administrator | Draft bounded extra time/attempts, review it and observe a matching student's new quiz session; then revoke. | Draft/future/expired/revoked records do not grant new adjustments; no stacking; existing session preserves its grant subject to closing time. No diagnoses entered. |
| Reporting reviewer | Capture a synthetic report snapshot and ask an independent authorized reviewer to approve its export. | Author cannot self-approve; changed department permissions are enforced at access/export; export matches the captured snapshot. |
| Security operator | Revoke one synthetic session, use authorized account controls with a reason, and track a fictional incident. | Other unrelated accounts stay unaffected; revoked sessions are denied; control history is preserved. Never practice lockout on the only recovery administrator. |
| Operations reviewer | Inspect protected metrics, a synthetic failed-notification state and verified recovery evidence. | Missing backup configuration is unhealthy, no secrets/record contents leak, and a passed synthetic restore is distinguished from offsite recovery acceptance. |

## Accessibility and recovery exercises

Ask participants to complete their workflows with keyboard-only input, zoom/reflow, supported mobile layouts and institution-selected assistive technology. Record barriers with the page, action and expected behavior. Five automated browser configurations and sampled axe checks do not establish comprehensive WCAG conformance, actual-device compatibility or screen-reader acceptance.

Rehearse interruption, stale form submission, expired assessment, permission revocation and rejected upload using synthetic cases. The application should explain the problem without disclosing another user's records or silently duplicating financial/academic actions. Report discrepancies through [troubleshooting](TROUBLESHOOTING.md); use [incident response](INCIDENT_RESPONSE.md) for suspected compromise or integrity failures.

## Signoff boundary

Each role owner must review its actual institutional policy and record acceptance or open issues. Privacy/security reviewers and infrastructure owners approve their own gates. Live SMTP, Stripe, identity, AI, signing trust, offsite recovery and institutional staging require separate authorized evidence. Training completion alone does not authorize stable v1.0.0. See [release status](RELEASE_STATUS.md) and the [master checklist](../MASTER_CHECKLIST.md).
