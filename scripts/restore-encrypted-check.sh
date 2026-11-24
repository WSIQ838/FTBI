#!/bin/sh
set -eu
umask 077
: "${FTBI_RESTORE_TEST_DB:?Set disposable database name}"
: "${BACKUP_AGE_IDENTITY_FILE:?Set private age identity file}"
: "${1:?Encrypted backup file required}"
case "$FTBI_RESTORE_TEST_DB" in ftbi_restore_test_*) ;; *) echo "Unsafe restore database name" >&2; exit 1;; esac
tmp=$(mktemp)
trap 'rm -f "$tmp"' EXIT HUP INT TERM
age -d -i "$BACKUP_AGE_IDENTITY_FILE" -o "$tmp" "$1"
pg_restore --list "$tmp" >/dev/null
pg_restore --exit-on-error --no-owner --no-acl --dbname="$FTBI_RESTORE_TEST_DB" "$tmp"
