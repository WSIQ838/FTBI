# Operational safeguards
Course reminders are opt-in at the institution level (FTBI_EMAIL_REMINDERS=1). Enable only when all populated user email addresses have been verified by authorized staff, SMTP is configured, and institutional notification policy permits sending. Run send_course_reminders daily from a single scheduler. Messages contain no coursework details. Successful sends are recorded per assignment and recipient; delivery is at-least-once because SMTP and database writes cannot share a transaction. A shared cache is required for multi-host locking.
Encrypted backups use the age public-key recipient and PostgreSQL custom format. A temporary plaintext dump is created in a private backup directory and removed at exit; use encrypted storage and monitor for abandoned temporary files after crashes. Example systemd units assume /opt/ftbi and a dedicated ftbi-backup user. Keep the decryption identity separate from backup storage. Copy encrypted backups offsite and define retention in accordance with institutional policy. Restore only to a disposable database and validate data, migrations and application login independently. The sample scheduler is not installed or running on a production host. Actual restore drills remain required.


## Monitoring and managed backup retention

See OBSERVABILITY.md for protected operational checks, transition alerts and scrubbed logs. See BACKUP_RETENTION.md for managed encrypted archives, restore-gated retention and failure status. Institutional schedulers, external uptime monitoring, offsite storage and recovery acceptance remain outstanding.

See [reviewed file retention](FILE_RETENTION.md) for disabled-by-default, independently reviewed obsolete-version erasure and preservation holds. This is separate from encrypted-backup retention; neither process proves physical erasure of all copies.
