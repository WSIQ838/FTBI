# Update and upgrade acceptance procedure

Draft review procedure for an already authorized deployment. No stable v1.0.0 or institutional production acceptance exists. This document does not provide installation or production execution instructions.

## Prepare a reviewable change

Record the current and proposed commit, application image digest, dependency changes, configuration differences and migration list. Review the change log and scope checklist; a green test run does not remove unfinished scope or institutional approvals. Identify data/schema compatibility, changed permissions, external provider behavior and user-visible differences. Assign an operator, academic/finance owner as applicable, recovery owner and decision authority.

## Rehearse before approval

Use a disposable isolated staging copy with institution-approved data handling; synthetic data is the default. Preserve and verify the backup, exact code version, required private media and separately controlled key references. Database-only recovery does not restore private attachments or signing keys. Review migration operations and rehearse both fresh migration and upgrade from the current schema. Do not assume a reverse migration preserves newly written records. Existing syncdb-created databases require schema comparison; never mark migrations applied merely to suppress errors.

Run regression and PostgreSQL concurrency checks, browser/accessibility sampling, dependency/static scans, production-mode service/scanner checks and encrypted restore verification against the proposed commit. Add focused checks for changed workflows. Obtain live-provider evidence where provider behavior changes. Record pass/fail evidence and limitations rather than copying a previous release's results.

## Decide and observe

The institutional decision must name the maintenance window, service/write restrictions, notification owner, recovery trigger and acceptable outage/data-loss objectives. Background workers and scheduled actions must be accounted for so mixed application versions do not process incompatible state. No scheduler or maintenance control is automatically deployed by this repository.

After an authorized change, compare the deployed commit and migration state with the reviewed artifact. Validate readiness, private operational checks, role-scoped login, a synthetic affected workflow and external integration health where approved. Preserve generic failure counts and references without student records or secrets. Release gates remain open until the relevant owners accept the evidence.

## Recover without hiding data loss

Choose forward repair when reverting code would be incompatible with the new schema or records. Reverting a Git commit does not roll back a database, uploaded files, external payments or sent messages. Restoring a backup can discard later writes and reintroduce revoked state; reconcile records, payments, notifications and account controls before resuming service. Recovery must use a verified backup and controlled keys with documented authorization and post-restore integrity checks. Record the outcome and corrective work in the incident/change history.

Institutional staging, maintenance automation, approved RTO/RPO, offsite recovery, key custody and production execution acceptance remain outstanding. See [migrations](MIGRATIONS.md), [backup retention](BACKUP_RETENTION.md), [testing](TESTING.md) and [release status](RELEASE_STATUS.md).
