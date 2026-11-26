# External integrations and acceptance boundaries

| Integration | Repository behavior | Outstanding acceptance |
| --- | --- | --- |
| Payments | Manual receipt review and optional hosted link; optional Stripe Checkout validates signed completed-session events and posts a once-only ledger credit. See [STRIPE.md](STRIPE.md) and [FINANCE.md](FINANCE.md). | Live test credentials/endpoint, provider refund/dispute workflows, bank settlement reconciliation and institutional finance/security approval. |
| Identity | Provisioned immutable-subject OIDC with trusted provider validation; local account and MFA controls remain. See [IDENTITY.md](IDENTITY.md). | Institutional test tenant, recovery process and independent MFA/SSO acceptance. |
| AI | Disabled-by-default approved configuration, bounded knowledge retrieval, budgets and metadata-only usage. See [AI_ASSISTANT.md](AI_ASSISTANT.md). | Live provider, pricing/budget approval, academic integrity and privacy/data agreements. |
| Email | Private in-app notices and approved-SMTP delivery worker with bounded retry; separate course reminders. See [ACCOUNT_SECURITY.md](ACCOUNT_SECURITY.md). | Approved sender/recipients, real delivery and failure tests, scheduler deployment. |
| Upload scanning | Private ClamAV protocol with fail-closed extended-format uploads; real clean/EICAR/unavailable-scanner CI checks. See [UPLOAD_SECURITY.md](UPLOAD_SECURITY.md). | Institutional private scanner deployment, maintenance and operational acceptance. |
| Credential signing | Exact PDF artifacts, optional required signing, verification/revocation; synthetic certificate signature and tamper tests. See [CREDENTIALS.md](CREDENTIALS.md). | Institutional certificate trust, protected keys, recipient validation and key custody. |

SCORM/xAPI, LTI, plagiarism, proctoring, accounting, SMS, external object storage and third-party transcript delivery are not complete. Mocked provider responses and synthetic CI services must never be presented as live institutional acceptance. Do not transmit student records to providers without applicable institutional authorization. See [release status](RELEASE_STATUS.md) for missing credentials, infrastructure and approvals.
