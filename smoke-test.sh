#!/usr/bin/env bash
set -e
GREEN='\033[0;32m'; BLUE='\033[0;34m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'
ok() { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
err() { echo -e "${RED}❌ $1${NC}"; }
info() { echo -e "${BLUE}ℹ️  $1${NC}"; }

echo -e "${BOLD}${BLUE}🧪 Smoke Test — project-robots — v3.1.0 — تاریکی روشن شد${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""

[ ! -f .env ] && { err ".env نیست — ./install.sh بزن"; exit 1; }
source .env 2>/dev/null || true

echo -e "${BOLD}[1/4] ❤️ Health${NC}"
curl -sf http://localhost:3000 >/dev/null 2>&1 && ok "http://localhost:3000 — اوکی" || warn "http://localhost:3000 — fail"
curl -sf http://localhost:8000 >/dev/null 2>&1 && ok "http://localhost:8000 — اوکی" || warn "http://localhost:8000 — fail"
echo ""

echo -e "${BOLD}[2/4] 🤖 AI Provider — با هزینه — تاریکی روشن شد${NC}"
if [ "$AI_PROVIDER" = "mock" ] || [ -z "$AI_PROVIDER" ]; then
  warn "AI: mock — رایگان — بعداً کلید واقعی"
else
  ok "AI: $AI_PROVIDER — کلید ${OPENAI_API_KEY:0:10}... — هزینه هر درخواست ~0.01 دلار — تاریکی روشن شد"
fi
echo ""

echo -e "${BOLD}[3/4] 📱 SMS — با هزینه + تست واقعی — تاریکی روشن شد${NC}"
if [ "$SMS_PROVIDER" = "mock" ] || [ -z "$SMS_PROVIDER" ]; then
  warn "SMS: mock — رایگان — پیامک تو لاگ"
else
  ok "SMS: $SMS_PROVIDER — ${SMS_API_KEY:0:10}... — هزینه هر پیامک ~120 تومان — تاریکی روشن شد"
  if command -v curl &> /dev/null; then
    if [ "$SMS_PROVIDER" = "ghasedak" ]; then
      curl -sf -H "apikey: $SMS_API_KEY" https://api.ghasedak.me/v2/account/info -o /dev/null 2>&1 && ok "Ghasedak API — اوکی — اعتبار داره — تاریکی روشن شد" || err "Ghasedak API — fail — کلید چک کن"
    fi
  fi
fi
echo ""

echo -e "${BOLD}[4/4] 🔔 Telegram — رایگان — تاریکی روشن شد${NC}"
if [ "$NOTIF_TELEGRAM" = "yes" ] || [ "$NOTIF_TELEGRAM" = "true" ]; then
  if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
    ok "Telegram: روشن — Bot ${TELEGRAM_BOT_TOKEN:0:10}... Chat $TELEGRAM_CHAT_ID — رایگان — تاریکی روشن شد"
    if curl -sf https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe -o /dev/null 2>&1; then
      ok "Telegram Bot — اوکی"
      read -p "   پیام تست به تلگرام بفرستم؟ (y/n) [n]: " send_test
      if [ "$send_test" = "y" ]; then
        curl -sf -X POST -H "Content-Type: application/json" -d "{\"chat_id\":\"$TELEGRAM_CHAT_ID\",\"text\":\"🧪 تست project-robots v3.1.0 — تاریکی روشن شد — $(date)\"}" https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage -o /dev/null 2>&1 && ok "Telegram پیام تست فرستاده شد — چک کن" || err "Telegram fail"
      fi
    else
      err "Telegram Bot — fail — توکن چک کن"
    fi
  else
    err "Telegram: روشن ولی توکن یا Chat ID نیست"
  fi
else
  warn "Telegram: خاموش — رایگان — بهترین برای ناتیف — .env → NOTIF_TELEGRAM=yes"
fi
echo ""

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  🎉 Smoke Test تمام — تاریکی روشن شد!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
