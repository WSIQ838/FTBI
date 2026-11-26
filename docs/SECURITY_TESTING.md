# Automated security and stack validation

The Security analysis workflow runs dependency advisory scanning and Bandit static analysis on pushes, pull requests and weekly. Medium/high severity and confidence findings fail the static gate. Reports are retained as CI artifacts. Development-only test credentials are not production secrets. Two reviewed URL-open calls use fixed URLs: the HTTPS AI provider and loopback container readiness; their narrow Bandit suppressions are documented inline. PDF display escaping uses the standard HTML escaping utility rather than XML imports.

The initial local dependency audit found no known vulnerabilities in its resolved dependencies on 2026-11-24. This is advisory-database evidence at that time, not a security guarantee or a substitute for review of future dependency resolutions.

The Production stack smoke workflow builds the application image, starts PostgreSQL and Redis, applies migrations, starts production-mode Gunicorn through Compose, probes shared cache and readiness, and performs a PostgreSQL dump/restore into a disposable database. It captures service logs and removes its CI volumes. It also starts real ClamAV and checks clean content, EICAR rejection and unavailable-scanner rejection. The separate Encrypted recovery drill uses disposable age keys, managed manifests and a restored synthetic dataset with all-application-row fingerprint comparison. Public Caddy TLS certificates, offsite durability, representative production-scale recovery, institutional key custody and a timed full disaster-recovery drill remain separate gates.

The advisory scan covers Python requirements resolved for that run; it does not constitute a container OS audit, a complete JavaScript supply-chain audit or independent dependency review. Record the exact commit/run and retained reports for each acceptance decision.

Independent authorization review, dynamic testing, authorized penetration testing, privacy acceptance, provider agreements and real institutional user acceptance remain outstanding. Automated scans do not close those gates.
