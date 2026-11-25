# Release status and external acceptance blockers

Status: **development; not v1.0.0 and not an accepted release candidate**.

The complete supplied scope is preserved in `MASTER_CHECKLIST.md`. Its inherited checkmarks describe previously reported implementation, not blanket verification or production acceptance. Newly verified work and exact CI evidence are recorded in pull requests. No optional enterprise requirement has been silently removed from scope.

Baseline confirmed: PR #21 merged into `55918912938420613bacaf5203a2e0aade0c381d`; main workflow run `45501305662` succeeded. Only 37 test methods existed at that point. Passing them is not comprehensive coverage of the full checklist.

## External gates

| Gate | Missing evidence or dependency | Required acceptance |
| --- | --- | --- |
| Scope completion | Many unchecked implementation items | Implement and verify each item, or obtain explicit scope changes |
| Stripe | No test account credentials or test webhook endpoint supplied; refund/dispute provider integration still unfinished | Test charge, replay, mismatch, refund, dispute and reconciliation evidence |
| Credential signing | No institutional certificate, protected secret mount or key-custody/trust acceptance supplied | Ephemeral-certificate PDF signature and tamper tests pass; institutional trust, rotation and recipient validation remain. HSM, trusted timestamps and long-term validation evidence are not implemented |
| SMTP | No approved outbound service or test recipients supplied | Deliver activation, reset and operational notifications; validate failure handling |
| OIDC | No institutional identity-provider test tenant supplied | Provisioned login, wrong issuer/audience, revoked user and logout tests |
| AI | No approved provider credentials/budget or institutional privacy approval supplied | Live provider tests and approved data handling, usage and budget controls |
| Infrastructure | Local Docker is unavailable; hosted production-mode PostgreSQL/Redis/Gunicorn smoke and encrypted synthetic-data restore passed (45551038947); real ClamAV checks passed (45551038958); no institutional staging host/domain supplied | Fresh production Compose start, HTTPS certificate, Redis, scanner, monitoring and resource checks |
| Recovery | No offsite storage, recovery keys or recovery objectives supplied | Scheduled encrypted backup, verified disposable restore and timed recovery drill |
| Security/privacy | No independent review or institutional policy acceptance supplied | Authorization review, vulnerability remediation, authorized penetration testing and privacy acceptance |
| Interoperability | No selected LTI, SCORM/xAPI, proctoring, plagiarism, accounting or SMS test providers supplied | Standards implementation plus provider-specific interoperability validation |
| Usability | No institutional UAT or assistive-technology acceptance evidence | Five browser configurations and sampled automated accessibility passed (45551039013); comprehensive assessment, screen-reader and role-based user acceptance remain |

These missing dependencies do not excuse unfinished local implementation. Mocked tests must be identified as mocked and cannot close live integration gates. No production database migrations have been run; local and CI migrations use disposable test/development databases.
