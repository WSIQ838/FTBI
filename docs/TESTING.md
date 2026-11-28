# Testing
CI runs migration drift checks, migrate, Django checks and the test suite on SQLite and PostgreSQL. View the Actions run for the exact commit before claiming success. Use synthetic records only. Unit tests and mocked services do not establish real provider, browser, load, accessibility, security or restore acceptance. See RELEASE_GATES.md.


## Browser validation

The Browser and accessibility validation workflow runs real Chromium, Firefox and WebKit engines, iPhone viewport emulation and dark mode. It uses an isolated database and synthetic accounts to verify keyboard skip navigation, login/logout, student submission, instructor grading, student feedback and denial of another student's course access. A separate records scenario covers a student appeal, independent reviewer grant, private outcome and denial of another student/staff-only access across the same five configurations. Axe checks WCAG 2/2.1 A/AA rules on login, dashboard, course, submission and grading pages; horizontal overflow is checked at each step. Reports, failure screenshots and traces are CI artifacts. These are sampled automated checks, not comprehensive WCAG conformance, real-device testing or screen-reader acceptance. See https://playwright.dev/docs/accessibility-testing for the tool's coverage limits.

The seed_demo management command refuses production mode and nonempty databases. It requires explicit demonstration enablement and a caller-supplied password of at least 16 characters. It creates synthetic students/faculty without administrator privileges, a course, lesson and assignment. With explicit browser-testing enablement, the fixture also creates five isolated records students, synthetic denied withdrawals and a non-staff reviewer with only three workflow permissions. These records are separate from the learning scenario so withdrawal does not invalidate its enrollment. Browser settings use a separate database, local email and disabled external providers; they must never be used for deployment.

## Recovery and scanner validation

Encrypted recovery drill creates a synthetic PostgreSQL dataset, encrypts a backup using the repository backup script and a disposable age key, restores through the encrypted restore script, and compares deterministic fingerprints of all application model rows. It also checks restored migrations. Private keys, database dumps and record contents are not uploaded as artifacts. This tests the scripts and synthetic data, not offsite durability, production scale, approved recovery objectives or institutional key custody.

Production stack smoke starts the real private ClamAV container. The application scanner must accept clean bytes, reject the harmless standard EICAR test signature, accept a subsequent clean scan and reject during an unavailable-scanner test. No real malware is used. The scanner port is not published to the host. Reference: https://docs.clamav.net/manual/Installing/Docker.html .

## Portal query growth

`academics.test_query_performance` compares warmed rendered requests with one versus 31 courses, and one versus 31 assignments/submissions/lessons in the same module. Related term/instructor, policy/rubric, attachment metadata and document queries must not grow per displayed item. Attachment binary payloads are excluded from these page queries. Module access decisions are reused only inside one request; permission/progress changes are rechecked on the next request. This is a query-count regression check, not a production latency, load, stress, memory-capacity or connection-pool acceptance test. Different module graphs still require further profiling.

## Bounded synthetic HTTP load

The Synthetic load validation workflow starts disposable PostgreSQL/Redis services, migrates an empty database, seeds guarded fictional accounts and serves Gunicorn with two workers/four threads each. The probe logs in once as a synthetic student and exercises dashboard, course, catalog and notification reads at 1, 4 and 12 concurrent workers, 120 requests per stage. It fails on any unexpected status/content/redirect or a stage p95 above 10 seconds. JSON artifacts report counts, throughput and latency percentiles without cookies, credentials or response bodies. The generous CI threshold detects severe regressions; it is not an institutional service-level objective.

The probe requires explicit disposable-test opt-in and the guarded synthetic fixture, accepts only numeric loopback HTTP origins, disables proxies, confines redirects to the same origin and caps request counts/workers/timeouts. Tests cover those guards, percentiles and fail-closed error reporting. It is not a generic tool for loading a public or production system.

These bounded ramps use one small synthetic course and one student session. They do not prove production capacity, multi-role/multi-user behavior, write-heavy workloads, sustained soak behavior, failover, connection-pool sizing or performance under an institution’s expected peak load. Representative datasets, approved load objectives and staged production-like acceptance remain outstanding.

## Dependency advisory checks

Security analysis runs independent Python and browser-tool dependency jobs. The JavaScript job installs the committed browser lockfile with lifecycle scripts disabled, then audits all installed dependencies including development tools. Any reported low-or-higher vulnerability or audit-service failure fails the job; the JSON report is retained even on failure. Python checks use pip-audit and Bandit. These automated results do not establish absence of vulnerabilities, container-image coverage or independent security acceptance.

## Passkey validation

Signed synthetic authenticator responses exercise the real WebAuthn verification library: accepted signatures, invalid origin/RP/challenge/signature/verification flags/backup eligibility, credential ownership and user-handle checks, expiring/session-bound challenges, replay, revocation, recovery, CSRF, rate limits and notification rollback. PostgreSQL additionally races the same assertion to require one successful consumption and audit event. The Chromium project runs an isolated account through browser enrollment, gated sign-in, verification and revocation using the browser's virtual CTAP2 authenticator; the other four projects continue their existing learning/records scenarios. This passkey scenario does not claim Firefox/WebKit, physical device, synced-provider or independent security acceptance.

## Isolated SMTP transport validation

The stack workflow includes a separate Mailpit v1.34.0 capture server with mandatory STARTTLS and synthetic authentication. A fresh SQLite database exercises the real delivery worker and SMTP backend: encrypted delivery, generic content, recipient isolation, opt-out, repeat safety, authentication failure, retry timing, untrusted certificate rejection, refused connections, recovery and the five-attempt terminal state. The fixture accepts only explicit test mode, fixed loopback endpoints, reserved synthetic addresses and an empty application database. Capture HTTP requests prohibit proxies, redirects and arbitrary paths.

Only a summary JSON artifact is retained; certificates, private keys and mailbox contents are disposable. No relay or forwarding is configured. A passing run proves the captured protocol scenarios, not institutional provider acceptance, DNS/domain authentication, deliverability, bounce processing, scheduler deployment or exactly-once email delivery. Provider selection and production acceptance remain open.
