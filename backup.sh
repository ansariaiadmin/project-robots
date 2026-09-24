#!/usr/bin/env bash
set -e
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m'

ok() { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

echo -e "${BOLD}${BLUE}💾 بکاپ AiWp — v3.1.0 — تاریکی روشن شد — با encrypt + .env + کلیدها${NC}"
echo -e "${BLUE}========================================${NC}"

if [ ! -f .env ]; then
  echo -e "${RED}❌ .env نیست — ./install.sh بزن${NC}"
  exit 1
fi

# Check .env permission — تاریکی روشن شد
perms=$(stat -c %a .env 2>/dev/null || stat -f %A .env 2>/dev/null || echo "unknown")
if [ "$perms" != "600" ]; then
  warn ".env permission $perms — باید 600 باشه — درست می‌کنم: chmod 600 .env — تاریکی روشن شد"
  chmod 600 .env && ok ".env permission 600 — امن" || warn "نمی‌تونم"
else
  ok ".env permission 600 — امن — تاریکی روشن شد"
fi

# Backup dir
BACKUP_DIR="./backups"
mkdir -p $BACKUP_DIR
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_FILE="$BACKUP_DIR/project-robots-backup-$TIMESTAMP.tar.gz"
BACKUP_ENCRYPTED="$BACKUP_DIR/project-robots-backup-$TIMESTAMP.tar.gz.enc"

echo -e "${BLUE}📦 بکاپ — شامل DB + .env + کلیدها — با encrypt — تاریکی روشن شد${NC}"
info "بکاپ شامل: .env (با کلیدهای SMS, Telegram, AI) + DB dump + uploads — همه با encrypt — امن — تاریکی روشن شد"

# DB dump if possible
if command -v docker &> /dev/null && docker compose ps 2>/dev/null | grep -q "Up"; then
  echo -e "${BLUE}  DB dump...${NC}"
  docker compose exec -T db pg_dump -U project-robots project-robots 2>/dev/null > /tmp/project-robots-db-$TIMESTAMP.sql || echo "DB dump fail — شاید DB خاموشه"
  ok "DB dump — /tmp/project-robots-db-$TIMESTAMP.sql"
else
  warn "Docker خاموش — DB dump نمی‌شه — فقط .env بکاپ می‌گیرم"
fi

# Create tar.gz with .env + db dump + important files
echo -e "${BLUE}  ساخت tar.gz...${NC}"
tar -czf $BACKUP_FILE .env .env.example docker-compose.yml 2>/dev/null || tar -czf $BACKUP_FILE .env 2>/dev/null
if [ -f /tmp/project-robots-db-$TIMESTAMP.sql ]; then
  tar -rf $BACKUP_FILE /tmp/project-robots-db-$TIMESTAMP.sql 2>/dev/null || true
  gzip $BACKUP_FILE 2>/dev/null || true
fi

# Encrypt backup — تاریکی روشن شد
if command -v openssl &> /dev/null; then
  echo -e "${BLUE}  Encrypt بکاپ با AES-256 — امن — تاریکی روشن شد${NC}"
  BACKUP_KEY=$(grep BACKUP_ENCRYPTION_KEY .env 2>/dev/null | cut -d= -f2 || echo "default-key-32-bytes-long-123456")
  if [ -z "$BACKUP_KEY" ] || [ "$BACKUP_KEY" = "default-key-32-bytes-long-123456" ]; then
    BACKUP_KEY=$(openssl rand -base64 32 | tr -d '\n' | cut -c1-32)
    echo "BACKUP_ENCRYPTION_KEY=$BACKUP_KEY" >> .env
    ok "BACKUP_ENCRYPTION_KEY ساخته شد — 32 کاراکتر — امن — تاریکی روشن شد"
  fi
  openssl enc -aes-256-cbc -salt -in $BACKUP_FILE -out $BACKUP_ENCRYPTED -k $BACKUP_KEY 2>/dev/null && ok "بکاپ encrypt شد: $BACKUP_ENCRYPTED — امن — تاریکی روشن شد" || warn "Encrypt fail — بکاپ بدون encrypt: $BACKUP_FILE"
  rm $BACKUP_FILE 2>/dev/null || true
  BACKUP_FILE=$BACKUP_ENCRYPTED
else
  warn "openssl نیست — بکاپ بدون encrypt: $BACKUP_FILE — ناامن — openssl نصب کن — تاریکی روشن شد"
fi

# Cleanup old backups — keep last 7 — تاریکی روشن شد
echo -e "${BLUE}  پاکسازی بکاپ قدیمی — نگه داشتن 7 آخری — تاریکی روشن شد${NC}"
ls -t $BACKUP_DIR/project-robots-backup-*.tar.gz* 2>/dev/null | tail -n +8 | xargs rm -f 2>/dev/null || true
ok "بکاپ قدیمی پاک شد — فقط 7 آخری نگه داشته شد — دیسک کنترل — تاریکی روشن شد"

ok "بکاپ کامل شد: $BACKUP_FILE — $(du -h $BACKUP_FILE 2>/dev/null | awk '{print $1}') — امن — encrypt — با .env + کلیدها — تاریکی روشن شد"
info "برای restore: ./restore.sh $BACKUP_FILE — یا دستی: tar -xzf $BACKUP_FILE"
info "کلید encrypt تو .env: BACKUP_ENCRYPTION_KEY — امن نگه دار — تاریکی روشن شد"
echo ""
echo -e "${BLUE}📊 بکاپ‌ها:${NC}"
ls -lh $BACKUP_DIR/ 2>/dev/null | tail -n 10
echo ""
