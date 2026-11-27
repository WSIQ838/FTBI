# Release status and external acceptance blockers

Status: **development; not v1.0.0 and not an accepted release candidate**.

The complete supplied scope is preserved in `MASTER_CHECKLIST.md`. Its inherited checkmarks describe previously reported implementation, not blanket verification or production acceptance. Newly verified work and exact CI evidence are recorded in pull requests. No optional enterprise requirement has been silently removed from scope.

Baseline confirmed: PR #21 merged into `55918912938420613bacaf5203a2e0aade0c381d`; main workflow run `45501305662` succeeded. Only 37 test methods existed at that point. Passing them is not comprehensive coverage of the full checklist.

## Latest confirmed verification

As of November 27, 2026 (America/Los_Angeles), main includes PR #49 at `30a83aba9d5fb0bd701245803ce57d251a461005`. No stable version has been published. The following are confirmed merged milestones, with checks evaluated on each change's exact head:

| Changes | Verified scope | Remaining limitation |
| --- | --- | --- |
| #38–#39 | Operational health/backup controls and course package v2 | External monitoring, offsite recovery, media and interoperability acceptance |
| #40–#41 | Approved exam accommodations and scheduled academic-risk checks, including PostgreSQL concurrency | Institutional accommodation policy and deployed scheduler acceptance |
| #42–#43 | Operational manuals, interface inventory and role-based training workbook | Institutional review and user training acceptance |
| #44 | Independent withdrawal appeals with atomic grant/waitlist handling | Other academic-record exception/correction workflows and institutional policy acceptance |
| #45–#46 | Bounded portal query growth and atomic concurrent-corequisite registration | Representative database tuning and production load objectives |
| #47 | Ownership-checked bounded personal file archives | Full portability scope and external data/privacy acceptance |
| #48 | Disabled-by-default obsolete file-version retention, independent review and preservation holds | Full student-record deletion/anonymization, backup erasure and institutional retention approval |
| #49 | Synthetic authenticated HTTP load probe on disposable PostgreSQL/Redis/Gunicorn | Representative multi-user writes, sustained load, failover and production capacity acceptance |

PR #48 passed all ten push/PR checks for `f5b679d854c731746bd15a376a62bf2443ad3053`. PR runs: [regression/migrations](https://github.com/WSIQ838/FTBI/actions/runs/45964100849), [browsers/accessibility](https://github.com/WSIQ838/FTBI/actions/runs/45964100924), [security analysis](https://github.com/WSIQ838/FTBI/actions/runs/45964100922), [encrypted recovery](https://github.com/WSIQ838/FTBI/actions/runs/45964100919), [production stack](https://github.com/WSIQ838/FTBI/actions/runs/45964100906). Migration 0024 adds the reviewed retention records; no institutional documents were erased.

PR #49 passed all twelve push/PR checks for `c99f2e6a37aaef235aa49623f823571d40b94fb4`, adding a sixth workflow. PR runs: [regression/migrations](https://github.com/WSIQ838/FTBI/actions/runs/45964758058), [browsers/accessibility](https://github.com/WSIQ838/FTBI/actions/runs/45964757956), [security analysis](https://github.com/WSIQ838/FTBI/actions/runs/45964757933), [encrypted recovery](https://github.com/WSIQ838/FTBI/actions/runs/45964757996), [production stack](https://github.com/WSIQ838/FTBI/actions/runs/45964757928), [synthetic load](https://github.com/WSIQ838/FTBI/actions/runs/45964758002). The load run completed 120 requests at each of 1, 4 and 12 workers without failures; p95 was 27.08, 52.64 and 148.63 milliseconds respectively. These are observed CI results for one small synthetic course and one authenticated session, not a service-level commitment.

These checks use synthetic data and disposable infrastructure. They do not establish institutional deployment, external-provider acceptance, complete checklist coverage or independent security/privacy approval.

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
