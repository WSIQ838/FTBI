# Versioned schema
The initial schema is committed in academics/migrations/0001_initial.py. CI checks for model changes without migrations and tests fresh databases on SQLite and PostgreSQL. Apply committed migrations using manage.py migrate. Existing databases created with --run-syncdb require a verified schema comparison and backup before adoption; never blindly fake migrations.
