# Admissions review and conversion

Verified applicants submit program applications and upload private supporting documents while an application is pending. Application details show document versions, verification decisions and scheduled or cancelled interviews. Only assigned reviewers, authorized managers and applicants can open those application details. Private review notes remain staff-only.

Admissions reviewers see unassigned applications and their assigned applications. Admissions Managers can assign reviewers and oversee all applications; combine that group with Admissions permissions. Reviewers must be active staff with admissions review permission. Final decisions and conversion use the same assignment scope. Privileged generic Application administration remains a separately supervised administrative surface.

Review notes are append-only in the portal. Interviews require an authorized staff interviewer, future times, a duration of at most eight hours, and no overlap for either participant. Scheduling and cancellation emit durable applicant notices. There is no external calendar synchronization or automatic meeting creation.

Authorized staff record acceptance or rejection. Decisions create durable private notifications and queued email notices; live SMTP acceptance is separate. Accepted applicants can be converted by a registrar with profile-creation permission. This creates a unique student identifier; identity verification remains a staff responsibility. The conversion CSV, restricted to application and student-profile reporting permissions, compares applications with student profiles in the same program. It indicates current conversion state, not historical funnel timing.

## Activation recovery

Public signup creates an explicit pending activation record. Recovery requires the username and email to match an eligible pending record, returns a generic response, and limits requests by network address. Resending rotates the token, invalidating previous links. Activation consumes the pending record. Deactivated students, staff accounts and previously activated applicants cannot use recovery to regain access.

Pending accounts created before migration 0013 have no activation marker and must be reviewed by admissions before a new pending activation record is provisioned through a controlled administrative process. The migration does not infer that every inactive account should be activatable. Institutional SMTP/domain credentials and actual delivery acceptance remain required.

Application fees and live payment integration, complete admissions reporting/UAT and institution-specific admissions document requirements remain outstanding.
