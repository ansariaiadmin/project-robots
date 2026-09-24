#!/usr/bin/env bash
set -e
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  PROJECT_ROBOTS — Level 5 Autonomous Engineer - آپدیت خودکار${NC}"
echo -e "${BLUE}  Auto Updater v1.0.1${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Backup
echo -e "${BLUE}[1/5] بکاپ گیری / Backup...${NC}"
BACKUP_DIR="./backups/$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
if [ -f .env ]; then
  cp .env "$BACKUP_DIR/.env.backup"
  echo -e "${GREEN}✓ .env بکاپ شد به $BACKUP_DIR${NC}"
fi
if [ -f docker-compose.yml ]; then
  docker compose ps > "$BACKUP_DIR/compose-ps-before.txt" 2>&1 || true
  docker compose logs --tail=100 > "$BACKUP_DIR/logs-before.txt" 2>&1 || true
fi
echo -e "${GREEN}✓ بکاپ در $BACKUP_DIR${NC}"
echo ""

# Check git
echo -e "${BLUE}[2/5] دریافت آخرین نسخه / Pulling latest...${NC}"
if [ -d .git ]; then
  git fetch origin main 2>&1 | tail -n 5
  CURRENT=$(git rev-parse HEAD 2>/dev/null | cut -c1-7)
  echo "نسخه فعلی / Current: $CURRENT"
  git pull origin main || echo -e "${YELLOW}Git pull ناموفق، ادامه با نسخه محلی / Git pull failed, continuing${NC}"
  NEW=$(git rev-parse HEAD 2>/dev/null | cut -c1-7)
  echo "نسخه جدید / New: $NEW"
  if [ "$CURRENT" = "$NEW" ]; then
    echo -e "${BLUE}شما از قبل آخرین نسخه را دارید / Already latest${NC}"
  else
    echo -e "${GREEN}✓ آپدیت کد به $NEW / Code updated to $NEW${NC}"
  fi
else
  echo -e "${YELLOW}.git یافت نشد، فقط Docker images آپدیت می‌شود / No .git, only docker images${NC}"
fi
echo ""

# Update deps
echo -e "${BLUE}[3/5] آپدیت وابستگی‌ها / Updating dependencies...${NC}"
if [ "cli" = "web" ] && [ -f docker-compose.yml ]; then
  echo "docker compose pull"
  docker compose pull 2>&1 | tail -n 10 || true
fi
echo ""

# Rebuild and restart
echo -e "${BLUE}[4/5] ساخت مجدد و اجرا / Rebuilding and restarting...${NC}"
if [ -f docker-compose.yml ]; then
  docker compose up --build -d
  echo ""
  echo -e "${BLUE}صبر 15 ثانیه / Waiting 15s...${NC}"
  sleep 15
  docker compose ps
else
  if [ -f requirements.txt ]; then
    source .venv/bin/activate 2>/dev/null || true
    pip install -r requirements.txt --upgrade 2>&1 | tail -n 10
  fi
  if [ -f package.json ]; then
    npm install 2>&1 | tail -n 10
    npm run build 2>&1 | tail -n 10 || true
  fi
fi
echo ""

# Verify
echo -e "${BLUE}[5/5] بررسی سلامت / Health check...${NC}"
sleep 5
if command -v curl &> /dev/null; then
  if curl -sf pytest --collect-only >/dev/null 2>&1 || curl -sf http://localhost:3000 >/dev/null 2>&1 || curl -sf http://localhost:8000 >/dev/null 2>&1 || curl -sf http://localhost:8080 >/dev/null 2>&1; then
    echo -e "${GREEN}✓ سرویس سالم است / Service healthy!${NC}"
    curl -sf pytest --collect-only 2>&1 | head -n 5 || true
  else
    echo -e "${RED}✗ هشدار: سلامت چک ناموفق / Warning: health check failed${NC}"
    echo "لاگ‌ها / Logs:"
    if [ -f docker-compose.yml ]; then
      docker compose logs --tail=50
    fi
    echo ""
    echo -e "${YELLOW}برای بازگردانی: cp $BACKUP_DIR/.env .env && docker compose up -d${NC}"
    echo -e "${YELLOW}To rollback: cp $BACKUP_DIR/.env .env && docker compose up -d${NC}"
  fi
else
  echo -e "${YELLOW}curl نصب نیست، وضعیت دستی چک کنید / curl not found, check manually${NC}"
  if [ -f docker-compose.yml ]; then
    docker compose ps
  fi
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ آپدیت تمام شد! / Update Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo "آدرس / URL: CLI: ./project-robots --help"
echo "بکاپ / Backup: $BACKUP_DIR"
echo ""
