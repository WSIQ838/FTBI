# Account and notification administration

Users can inspect tracked browser sessions and revoke a session. Browser labels come from the client and are informational, not trusted device identities. Revocation is enforced on its next authenticated request. Revoking a session does not revoke other browsers. Session records do not contain authentication cookies.

Staff with the Security Administration permissions can revoke all sessions, lock accounts and unlock them. The action requires password confirmation and a reason, which is retained in an immutable account-control event. Only a superuser can control another superuser. Administrative locks also invalidate existing sessions; temporary failed-login locks block subsequent password sign-ins for 15 minutes. Ten failures within a rolling 15-minute window trigger a temporary lock, in addition to the existing address/username rate limit. This can be abused to temporarily deny a known account access; account support must review lockout patterns.

A changed network address triggers a generic security notice. It is a heuristic, not proof of account compromise. Only a digest of the most recent network address is stored. Password changes queue a notice. The institution still needs independent MFA, account-recovery and authorization review. Optional user-verified passkeys support a second factor after sign-in, enrollment/revocation and existing recovery codes; see MFA.md. Passwordless login and trusted-device bypass are not implemented.

Security incidents have an owner, severity and open/investigating/contained/resolved status in Administration. Updates queue notices to the owner. Incident records and audit events are not an external tamper-resistant log.

## Durable notifications

Notification history is private to its recipient and includes admissions decisions, registration confirmation, waitlist promotion, final-grade availability, confirmed payments and account security events. Duplicate event keys suppress duplicate records. Email preferences can disable outbound email while retaining in-app notices. No scores, admission outcomes, payment amounts or private message bodies are included in outbound email.

The delivery worker refuses to run without approved SMTP configuration. Failed delivery keeps attempt history and retries with increasing delay, up to five attempts. Permitted administrators can request a retry of failed items from notification administration. SMTP is at-least-once delivery: a provider may accept a message immediately before the connection fails, so an email retry can duplicate delivery. Live SMTP delivery and scheduler deployment remain unverified.

The existing assignment-reminder command is separate; its behavior remains documented in OPERATIONS.md. SMS is not implemented.
