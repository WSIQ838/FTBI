#!/bin/sh
# Restore into a disposable, empty test database only. Never production.
set -eu
: "${FTBI_RESTORE_TEST_DB:?Set disposable database name}"
case "$FTBI_RESTORE_TEST_DB" in ftbi_restore_test_*) ;; *) echo "Unsafe database name" >&2; exit 1;; esac
: "${1:?Backup file required}"
pg_restore --exit-on-error --no-owner --no-acl --dbname="$FTBI_RESTORE_TEST_DB" "$1"
