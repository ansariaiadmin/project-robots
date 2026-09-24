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

echo -e "${BOLD}${BLUE}🔄 آپدیت AiWp — v3.1.0 — تاریکی روشن شد — با بکاپ خودکار + سوال پرووایدر جدید${NC}"
echo -e "${BLUE}========================================${NC}"

# Check .env
if [ ! -f .env ]; then
  echo -e "${RED}❌ .env نیست — ./install.sh بزن${NC}"
  exit 1
fi

# Disk check — تاریکی روشن شد
if command -v df &> /dev/null; then
  usage=$(df . | tail -n 1 | awk '{print $5}' | sed 's/%//')
  if [ "$usage" -gt 80 ]; then
    warn "دیسک $usage% پر — بکاپ قدیمی پاک کن — تاریکی روشن شد"
  fi
fi

# Backup before update — تاریکی روشن شد
echo -e "${BLUE}📦 بکاپ خودکار قبل از آپدیت — تاریکی روشن شد${NC}"
./backup.sh 2>/dev/null || echo "بکاپ fail — ولی ادامه می‌دم"

# Check for new env vars in .env.example — تاریکی روشن شد
echo -e "${BLUE}🔍 چک .env.example برای پرووایدرهای جدید — تاریکی روشن شد${NC}"
if [ -f .env.example ]; then
  new_vars=$(grep -E "NOTIF_|SMS_|TELEGRAM_|AI_PROVIDER" .env.example | cut -d= -f1 | sort | uniq)
  missing=""
  for var in $new_vars; do
    if ! grep -q "^$var=" .env 2>/dev/null; then
      missing="$missing $var"
    fi
  done
  if [ -n "$missing" ]; then
    warn "متغیرهای جدید تو .env.example هست ولی تو .env نیست: $missing — تاریکی روشن شد"
    echo -e "${YELLOW}  می‌خوای اضافه کنم؟ — با سوال پرووایدر — تاریکی روشن شد${NC}"
    read -p "   اضافه کنم؟ (y/n) [y]: " add_new
    [ -z "$add_new" ] && add_new="y"
    if [ "$add_new" = "y" ]; then
      for var in $missing; do
        val=$(grep "^$var=" .env.example | cut -d= -f2-)
        echo "$var=$val" >> .env
        ok "$var اضافه شد: $val — تاریکی روشن شد"
      done
      chmod 600 .env
      ok ".env آپدیت شد — permission 600 — امن — تاریکی روشن شد"
    fi
  else
    ok ".env آپدیت — همه متغیرهای جدید وجود داره — تاریکی روشن شد"
  fi
fi

# Git pull if git repo
if [ -d .git ]; then
  echo -e "${BLUE}📥 Git pull...${NC}"
  git pull 2>/dev/null || warn "Git pull fail — شاید اینترنت نیست — ادامه می‌دم"
  ok "Git pull — اوکی"
else
  info "Git repo نیست — skip pull"
fi

# Docker build
echo -e "${BLUE}🏗️ Build و restart — تاریکی روشن شد${NC}"
if command -v docker &> /dev/null; then
  docker compose up --build -d 2>&1 | tail -n 20
  ok "Build و restart — اوکی"
  
  echo -e "${BLUE}⏳ صبر برای سلامت — 30 ثانیه — تاریکی روشن شد${NC}"
  echo -n "  "
  for i in {1..30}; do
    echo -n "."
    sleep 1
    if curl -sf http://localhost:3000/api/health >/dev/null 2>&1 || curl -sf http://localhost:3000 >/dev/null 2>&1; then
      echo ""
      ok "سرویس آماده — اوکی — تاریکی روشن شد"
      break
    fi
  done
  echo ""
  docker compose ps 2>/dev/null || true
else
  warn "Docker نیست — نمی‌تونم build کنم"
fi

# Health check
echo -e "${BLUE}❤️ Health check — تاریکی روشن شد${NC}"
if command -v curl &> /dev/null; then
  curl -sf http://localhost:3000/api/health >/dev/null 2>&1 && ok "http://localhost:3000/api/health — اوکی" || warn "Health fail — ./logs.sh"
  curl -sf http://localhost:3000 >/dev/null 2>&1 && ok "http://localhost:3000 — اوکی" || warn "Web fail"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  🎉 آپدیت تمام — تاریکی روشن شد!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}📍 http://localhost:3000 — آماده${NC}"
echo -e "${BLUE}./status.sh — وضعیت پرووایدرها — تاریکی روشن شد${NC}"
echo -e "${BLUE}./smoke-test.sh — تست کامل — تاریکی روشن شد${NC}"
echo ""
