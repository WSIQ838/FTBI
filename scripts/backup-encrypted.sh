#!/bin/sh
# Requires PostgreSQL client and age. Recipient is a public age key, never a private key.
set -eu
umask 077
: "${BACKUP_DIR:?Set private backup directory}"
: "${BACKUP_AGE_RECIPIENT:?Set age public recipient}"
mkdir -p "$BACKUP_DIR"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
tmp=$(mktemp "$BACKUP_DIR/.ftbi.XXXXXX")
plain=$(mktemp "$BACKUP_DIR/.plain.XXXXXX")
trap 'rm -f "$tmp" "$plain"' EXIT HUP INT TERM
pg_dump --format=custom --no-owner --no-acl --file="$plain"
pg_restore --list "$plain" >/dev/null
age -r "$BACKUP_AGE_RECIPIENT" -o "$tmp" "$plain"
test -s "$tmp"
mv "$tmp" "$BACKUP_DIR/ftbi-$stamp.dump.age"
