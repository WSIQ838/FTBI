#!/bin/sh
# Run in a trusted environment with PostgreSQL connection variables and pg_dump.
set -eu
umask 077
: "${BACKUP_DIR:?Set private backup directory}"
mkdir -p "$BACKUP_DIR"
stamp=$(date -u +%Y%m%dT%H%M%SZ)
tmp=$(mktemp "$BACKUP_DIR/.ftbi.XXXXXX")
trap 'rm -f "$tmp"' EXIT HUP INT TERM
pg_dump --format=custom --no-owner --no-acl --file="$tmp"
pg_restore --list "$tmp" >/dev/null
mv "$tmp" "$BACKUP_DIR/ftbi-$stamp.dump"
