# Admissions review and conversion

Verified applicants submit program applications and upload private supporting documents while an application is pending. Application details show document versions, verification decisions and scheduled or cancelled interviews. Only assigned reviewers, authorized managers and applicants can open those application details. Private review notes remain staff-only.

Admissions reviewers see unassigned applications and their assigned applications. Admissions Managers can assign reviewers and oversee all applications; combine that group with Admissions permissions. Reviewers must be active staff with admissions review permission. Final decisions and conversion use the same assignment scope. Generic Application administration cannot set a decision or delete applications; decided applications are read-only. Pending application maintenance remains a separately supervised administrative surface.

Review notes are append-only in the portal. Interviews require an authorized staff interviewer, future times, a duration of at most eight hours, and no overlap for either participant. Scheduling and cancellation emit durable applicant notices. There is no external calendar synchronization or automatic meeting creation.

Authorized staff record acceptance or rejection. Decisions create durable private notifications and queued email notices; live SMTP acceptance is separate. Accepted applicants can be converted by a registrar with profile-creation permission. This creates a unique student identifier; identity verification remains a staff responsibility. The conversion CSV, restricted to application and student-profile reporting permissions, compares applications with student profiles in the same program. It indicates current conversion state, not historical funnel timing.

## Activation recovery

Public signup creates an explicit pending activation record. Recovery requires the username and email to match an eligible pending record, returns a generic response, and limits requests by network address. Resending rotates the token, invalidating previous links. Activation consumes the pending record. Deactivated students, staff accounts and previously activated applicants cannot use recovery to regain access.

Pending accounts created before migration 0013 have no activation marker and must be reviewed by admissions before a new pending activation record is provisioned through a controlled administrative process. The migration does not infer that every inactive account should be activatable. Institutional SMTP/domain credentials and actual delivery acceptance remain required.

Application fees and live payment integration, complete admissions reporting/UAT and institution-specific admissions document requirements remain outstanding.

## Preserved decision letters

New acceptance and rejection decisions capture the applicant name, program, institution, decision date and exact public letter wording in the same transaction as the decision, audit event and durable notification. Later template, account, program or institutional-name changes do not change that captured letter. Repeat or competing decisions cannot replace it. Private review notes are never included.

Credential-template administrators can configure separate **Admissions acceptance** and **Admissions rejection** templates. Plain heading, body and footer support {recipient}, {program}, {institution}, {issued_date} and {identifier}. Enabling requires a nonblank institutional approval reference. Formatting expressions and attribute access are rejected; HTML is displayed as text. An invalid enabled template blocks the decision before any status, letter, audit or notification is saved. Missing or disabled templates use standard wording; the canonical decision is displayed independently of custom text.

Only the applicant can open the private letter route, as before. These are portal letters, not signed PDF artifacts. Decisions made before this change retain their existing display and carry a notice that current account/program information is used. Migration does not fabricate historical wording or decision dates. Corrections, reissued decisions, broader document templates, institutional wording approval and live SMTP acceptance remain outstanding.
