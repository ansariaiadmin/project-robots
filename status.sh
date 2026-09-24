#!/usr/bin/env bash
set -e
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

ok() { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
err() { echo -e "${RED}❌ $1${NC}"; }
info() { echo -e "${BLUE}ℹ️  $1${NC}"; }
explain() { echo -e "${CYAN}   💡 $1${NC}"; }

echo -e "${BOLD}${BLUE}📊 وضعیت project-robots — Status Check v3.1.0 — تاریکی روشن شد${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

# Docker
echo -e "${BOLD}🐳 Docker — جعبه جادویی${NC}"
if command -v docker &> /dev/null; then
  ok "Docker: $(docker --version)"
  docker compose ps 2>/dev/null || warn "docker compose ps failed — شاید خاموشه — ./start.sh بزن"
else
  err "Docker نیست — https://docs.docker.com/get-docker/"
fi
echo ""

# Ports
echo -e "${BOLD}🌐 پورت‌ها — Ports${NC}"
for port in 3000 5432 6379 8080; do
  if command -v lsof &> /dev/null; then
    if lsof -i :$port &> /dev/null; then
      ok "Port $port — اشغال — در حال استفاده"
    else
      warn "Port $port — آزاد — شاید سرویس خاموشه"
    fi
  elif command -v ss &> /dev/null; then
    if ss -tuln | grep -q ":$port "; then
      ok "Port $port — اشغال"
    else
      warn "Port $port — آزاد"
    fi
  else
    info "Port $port — نمی‌تونم چک کنم — lsof یا ss نصب نیست"
  fi
done
echo ""

# .env
echo -e "${BOLD}🔑 فایل تنظیمات — .env — امنیت${NC}"
if [ -f .env ]; then
  ok ".env وجود دارد — $(wc -l < .env) خط"
  perms=$(stat -c %a .env 2>/dev/null || stat -f %A .env 2>/dev/null || echo "unknown")
  if [ "$perms" = "600" ]; then
    ok ".env permission 600 — امن — فقط خودت می‌تونی بخونی — تاریکی روشن شد"
  else
    warn ".env permission $perms — باید 600 باشه — امن نیست — درست می‌کنم: chmod 600 .env"
    chmod 600 .env 2>/dev/null && ok ".env permission درست شد: 600" || warn "نمی‌تونم permission درست کنم"
  fi
  # Check required vars
  for var in DATABASE_URL NEXTAUTH_SECRET ENCRYPTION_KEY; do
    if grep -q "^$var=" .env; then
      ok "$var — تنظیم شده"
    else
      err "$var — نیست — .env خرابه — rm .env && ./install.sh"
    fi
  done
else
  err ".env نیست — ./install.sh بزن"
fi
echo ""

# Providers — تاریکی روشن شد
echo -e "${BOLD}🤖 پرووایدرها — Providers — تاریکی روشن شد${NC}"
if [ -f .env ]; then
  source .env 2>/dev/null || true
  
  # AI Provider
  echo -e "${CYAN}  AI Provider:${NC}"
  if [ -n "$AI_PROVIDER" ] && [ "$AI_PROVIDER" != "mock" ]; then
    if [ -n "$OPENAI_API_KEY" ] || [ -n "$ANTHROPIC_API_KEY" ]; then
      ok "  AI: $AI_PROVIDER — کلید تنظیم شده — ${OPENAI_API_KEY:0:12}... یا ${ANTHROPIC_API_KEY:0:12}..."
      explain "  هزینه: OpenAI هر افزونه ~0.05 دلار — Anthropic ~0.03 دلار — mock رایگان"
      # Test OpenAI
      if [ "$AI_PROVIDER" = "openai" ] && [ -n "$OPENAI_API_KEY" ] && command -v curl &> /dev/null; then
        echo -e "${CYAN}   تست اتصال OpenAI...${NC}"
        if curl -sf -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models -o /dev/null 2>&1; then
          ok "  OpenAI API — اوکی — اعتبار داره"
        else
          err "  OpenAI API — خطا — کلید چک کن — https://platform.openai.com/api-keys"
        fi
      fi
    else
      warn "  AI: $AI_PROVIDER — کلید نیست — mock می‌شه — /admin/settings/ai-provider"
    fi
  else
    warn "  AI: mock — بدون AI واقعی — بعداً از /admin/settings/ai-provider اضافه کن — رایگان"
  fi

  # SMS Provider — تاریکی روشن شد — تست واقعی
  echo -e "${CYAN}  SMS Provider:${NC}"
  if [ -n "$SMS_PROVIDER" ] && [ "$SMS_PROVIDER" != "mock" ]; then
    if [ -n "$SMS_API_KEY" ]; then
      ok "  SMS: $SMS_PROVIDER — کلید ${SMS_API_KEY:0:10}... — Sender: ${SMS_SENDER:-نامشخص}"
      explain "  هزینه: هر پیامک ~120 تومان — اعتبار چک می‌شه"
      # Real test for Ghasedak/Kavenegar
      if [ "$SMS_PROVIDER" = "ghasedak" ] && command -v curl &> /dev/null; then
        echo -e "${CYAN}   تست اتصال Ghasedak...${NC}"
        if curl -sf -H "apikey: $SMS_API_KEY" https://api.ghasedak.me/v2/account/info -o /dev/null 2>&1; then
          ok "  Ghasedak API — اوکی — اعتبار داره"
          # Try to get balance
          balance=$(curl -s -H "apikey: $SMS_API_KEY" https://api.ghasedak.me/v2/account/info | grep -o '"balance":[0-9]*' | cut -d: -f2 || echo "نامشخص")
          info "  اعتبار: $balance تومان (تقریبی)"
        else
          err "  Ghasedak API — خطا — کلید چک کن — https://ghasedak.me/ → داشبورد → API"
        fi
      elif [ "$SMS_PROVIDER" = "kavenegar" ] && command -v curl &> /dev/null; then
        echo -e "${CYAN}   تست اتصال Kavenegar...${NC}"
        if curl -sf https://api.kavenegar.com/v1/$SMS_API_KEY/account/info.json -o /dev/null 2>&1; then
          ok "  Kavenegar API — اوکی"
        else
          err "  Kavenegar API — خطا — کلید چک کن"
        fi
      fi
    else
      err "  SMS: $SMS_PROVIDER — کلید نیست — /admin/settings/sms-gateway"
    fi
  else
    warn "  SMS: mock — بدون پیامک واقعی — پیامک‌ها تو لاگ — بعداً از /admin/settings/sms-gateway — رایگان"
  fi

  # Email
  echo -e "${CYAN}  Email Provider:${NC}"
  if [ -n "$EMAIL_PROVIDER" ] && [ "$EMAIL_PROVIDER" != "mock" ]; then
    ok "  Email: $EMAIL_PROVIDER — $SMTP_USER @ $SMTP_HOST:$SMTP_PORT"
    if command -v curl &> /dev/null && [ -n "$SMTP_HOST" ]; then
      echo -e "${CYAN}   تست اتصال SMTP $SMTP_HOST:$SMTP_PORT...${NC}"
      if timeout 5 bash -c "cat < /dev/null > /dev/tcp/$SMTP_HOST/$SMTP_PORT" 2>/dev/null; then
        ok "  SMTP $SMTP_HOST:$SMTP_PORT — اوکی — وصل می‌شه"
      else
        warn "  SMTP $SMTP_HOST:$SMTP_PORT — وصل نمی‌شه — Host یا Port چک کن — یا Firewall"
      fi
    fi
  else
    warn "  Email: mock — بدون ایمیل واقعی — تو لاگ — بعداً SMTP اضافه کن — رایگان"
  fi

  # Telegram — تاریکی روشن شد
  echo -e "${CYAN}  Telegram Bot:${NC}"
  if [ "$NOTIF_TELEGRAM" = "yes" ] || [ "$NOTIF_TELEGRAM" = "true" ]; then
    if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
      ok "  Telegram: روشن — Bot ${TELEGRAM_BOT_TOKEN:0:10}... Chat $TELEGRAM_CHAT_ID"
      if command -v curl &> /dev/null; then
        echo -e "${CYAN}   تست اتصال Telegram...${NC}"
        if curl -sf https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe -o /dev/null 2>&1; then
          ok "  Telegram Bot API — اوکی — ربات وجود داره"
          # Check chat
          if curl -sf -X POST -H "Content-Type: application/json" -d "{\"chat_id\":\"$TELEGRAM_CHAT_ID\",\"text\":\"🔔 تست project-robots — Status Check — $(date)\"}" https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage -o /dev/null 2>&1; then
            ok "  Telegram Chat $TELEGRAM_CHAT_ID — اوکی — پیام تست فرستاده شد — تلگرامت رو چک کن"
          else
            err "  Telegram Chat $TELEGRAM_CHAT_ID — خطا — Chat ID چک کن — ربات رو استارت کردی؟ — https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getUpdates"
          fi
        else
          err "  Telegram Bot API — خطا — توکن چک کن — @BotFather → /newbot"
        fi
      fi
    else
      err "  Telegram: روشن ولی توکن یا Chat ID نیست — .env چک کن"
    fi
  else
    warn "  Telegram: خاموش — اگر می‌خوای وقتی فروش جدید میاد تلگرام خبر بده — .env → NOTIF_TELEGRAM=yes + TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID"
  fi

  # Notification System
  echo -e "${CYAN}  Notification System:${NC}"
  if [ "$NOTIF_IN_APP" = "true" ] || [ "$NOTIF_IN_APP" = "yes" ]; then
    ok "  In-App: همیشه روشن — تو داشبورد می‌بینی"
  else
    warn "  In-App: خاموش — باید روشن باشه"
  fi
  [ "$NOTIF_EMAIL" = "yes" ] || [ "$NOTIF_EMAIL" = "true" ] && ok "  Email Notif: روشن" || warn "  Email Notif: خاموش"
  [ "$NOTIF_SMS" = "yes" ] || [ "$NOTIF_SMS" = "true" ] && ok "  SMS Notif: روشن" || warn "  SMS Notif: خاموش"
fi
echo ""

# Health
echo -e "${BOLD}❤️ سلامت — Health${NC}"
if command -v curl &> /dev/null; then
  if curl -sf http://localhost:3000/api/health >/dev/null 2>&1; then
    ok "http://localhost:3000/api/health — اوکی — سرویس روشنه"
  else
    warn "http://localhost:3000/api/health — جواب نمی‌ده — شاید هنوز بالا نیومده — 30 ثانیه صبر کن — یا ./logs.sh"
  fi
  if curl -sf http://localhost:3000 >/dev/null 2>&1; then
    ok "http://localhost:3000 — اوکی — وب روشنه"
  else
    warn "http://localhost:3000 — جواب نمی‌ده"
  fi
else
  info "curl نیست — نمی‌تونم health چک کنم"
fi
echo ""

# Disk + Memory
echo -e "${BOLD}💾 دیسک + حافظه — تاریکی روشن شد${NC}"
if command -v df &> /dev/null; then
  df -h . | tail -n 1 | awk '{print "  دیسک: " $4 " آزاد از " $2 " — " $5 " استفاده شده"}'
  usage=$(df . | tail -n 1 | awk '{print $5}' | sed 's/%//')
  if [ "$usage" -gt 80 ]; then
    warn "  دیسک $usage% پر — بکاپ قدیمی رو پاک کن — ./backup.sh"
  else
    ok "  دیسک اوکی — $usage% استفاده"
  fi
fi
if command -v free &> /dev/null; then
  free -h | grep Mem | awk '{print "  حافظه: " $3 " استفاده از " $2}'
fi
echo ""

# Final
echo -e "${BOLD}${BLUE}🎯 خلاصه — چی کار کنم؟${NC}"
echo -e "${CYAN}  اگر همه ✅ — عالی — برو http://localhost:3000${NC}"
echo -e "${CYAN}  اگر ⚠️ — mock — بعداً از /admin/settings اضافه کن — رایگان${NC}"
echo -e "${CYAN}  اگر ❌ — .env چک کن — یا ./install.sh دوباره بزن — یا ./logs.sh${NC}"
echo ""
echo -e "${BOLD}🛠️ دستورات:${NC}"
echo -e "  ./logs.sh — لاگ"
echo -e "  ./stop.sh / ./start.sh — خاموش/روشن"
echo -e "  ./update.sh — آپدیت"
echo -e "  ./backup.sh — بکاپ"
echo -e "  ./smoke-test.sh — تست کامل همه پرووایدرها — تاریکی روشن شد — جدید v3.1.0"
echo ""
