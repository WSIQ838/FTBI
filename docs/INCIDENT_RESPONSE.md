# Incident response operating procedure

This is a draft for institutional acceptance. Assign a security owner, escalation contacts, privacy lead, communications approver and recovery operator before production.

1. Record an incident reference, time, severity, affected services and evidence source. Avoid copying credentials or unnecessary student information into incident notes.
2. Preserve relevant audit exports and infrastructure logs in institution-controlled evidence storage. Restrict access and record collection times; application database audit rows are not tamper-proof evidence.
3. Contain confirmed account compromise using account locks and session revocation. Rotate affected provider credentials through the approved secret store. Preserve evidence before changing or restoring systems.
4. Investigate the affected identities, records, time window and external providers. Have the institutional privacy/legal owner determine notification duties and recipients; this repository does not establish those obligations.
5. Correct the cause, run regression and security checks, and validate recovery in staging. Restore only from an approved verified backup and confirm access controls, integrity and service health.
6. Obtain the incident owner's approval to restore access. Track communications, recovery timing, remaining risks and follow-up actions. Resolve the incident after documented validation.

External evidence storage, monitoring/alerts, response contacts, retention rules and institutional approval remain deployment dependencies. Do not claim this document constitutes a penetration test or privacy certification.
