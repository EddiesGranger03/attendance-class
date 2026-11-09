#!/usr/bin/env bash
# Khôi phục từ file .dump. GHI ĐÈ dữ liệu hiện có trong database đích.
# Dùng:  DATABASE_URL=postgresql://... ./scripts/restore.sh backups/attendance_xxx.dump
set -euo pipefail
: "${DATABASE_URL:?Hãy đặt biến DATABASE_URL}"
FILE="${1:?Cần đường dẫn file .dump}"
[ -f "$FILE" ] || { echo "Không thấy file: $FILE"; exit 1; }
URL="${DATABASE_URL/postgresql+psycopg2:/postgresql:}"
echo "CẢNH BÁO: sẽ ghi đè dữ liệu trong database đích từ $FILE"
read -r -p "Gõ 'RESTORE' để tiếp tục: " ANSWER
[ "$ANSWER" = "RESTORE" ] || { echo "Đã huỷ."; exit 1; }
pg_restore --clean --if-exists --no-owner --no-privileges --dbname="$URL" "$FILE"
echo "Khôi phục xong. Hãy kiểm tra /health và số bản ghi."
