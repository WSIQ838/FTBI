# Testing
CI runs migration drift checks, migrate, Django checks and the test suite on SQLite and PostgreSQL. View the Actions run for the exact commit before claiming success. Use synthetic records only. Unit tests and mocked services do not establish real provider, browser, load, accessibility, security or restore acceptance. See RELEASE_GATES.md.


## Browser validation

The Browser and accessibility validation workflow runs real Chromium, Firefox and WebKit engines, iPhone viewport emulation and dark mode. It uses an isolated database and synthetic accounts to verify keyboard skip navigation, login/logout, student submission, instructor grading, student feedback and denial of another student's course access. Axe checks WCAG 2/2.1 A/AA rules on login, dashboard, course, submission and grading pages; horizontal overflow is checked at each step. Reports, failure screenshots and traces are CI artifacts. These are sampled automated checks, not comprehensive WCAG conformance, real-device testing or screen-reader acceptance. See https://playwright.dev/docs/accessibility-testing for the tool's coverage limits.

The seed_demo management command refuses production mode and nonempty databases. It requires explicit demonstration enablement and a caller-supplied password of at least 16 characters. It creates synthetic students/faculty without administrator privileges, a course, lesson and assignment. Browser settings use a separate database, local email and disabled external providers; they must never be used for deployment.

## Recovery and scanner validation

Encrypted recovery drill creates a synthetic PostgreSQL dataset, encrypts a backup using the repository backup script and a disposable age key, restores through the encrypted restore script, and compares deterministic fingerprints of all application model rows. It also checks restored migrations. Private keys, database dumps and record contents are not uploaded as artifacts. This tests the scripts and synthetic data, not offsite durability, production scale, approved recovery objectives or institutional key custody.

Production stack smoke starts the real private ClamAV container. The application scanner must accept clean bytes, reject the harmless standard EICAR test signature, accept a subsequent clean scan and reject during an unavailable-scanner test. No real malware is used. The scanner port is not published to the host. Reference: https://docs.clamav.net/manual/Installing/Docker.html .
