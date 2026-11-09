#!/usr/bin/env bash
# Backup PostgreSQL -> file .dump (định dạng custom của pg_dump).
# Dùng:  DATABASE_URL=postgresql://user:pass@host:5432/db ./scripts/backup.sh [thư_mục] [số_bản_giữ]
set -euo pipefail
: "${DATABASE_URL:?Hãy đặt biến DATABASE_URL}"
OUT_DIR="${1:-backups}"
KEEP="${2:-14}"
mkdir -p "$OUT_DIR"
FILE="$OUT_DIR/attendance_$(date -u +%Y%m%d_%H%M%S).dump"
# pg_dump không hiểu driver "postgresql+psycopg2://"
URL="${DATABASE_URL/postgresql+psycopg2:/postgresql:}"
pg_dump --format=custom --no-owner --no-privileges --dbname="$URL" --file="$FILE"
# Kiểm tra file đọc được
pg_restore --list "$FILE" > /dev/null
echo "OK: $FILE ($(du -h "$FILE" | cut -f1))"
# Giữ N bản mới nhất
ls -1t "$OUT_DIR"/attendance_*.dump 2>/dev/null | tail -n +"$((KEEP + 1))" | xargs -r rm -f
