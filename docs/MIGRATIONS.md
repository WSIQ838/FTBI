# Versioned schema
The initial schema is committed in academics/migrations/0001_initial.py. CI checks for model changes without migrations and tests fresh databases on SQLite and PostgreSQL. Apply committed migrations using manage.py migrate. Existing databases created with --run-syncdb require a verified schema comparison and backup before adoption; never blindly fake migrations.

Migration 0013 adds private document versions, quotas, admissions support and explicit pending applicant activation markers. Existing inactive accounts are intentionally not automatically marked activatable. Existing coursework attachments remain readable through their original route. No production data migrations have been executed during development.
