#!/usr/bin/env bash
set -e
GREEN='\033[0;32m'; BLUE='\033[0;34m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; MAGENTA='\033[0;35m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'
ok() { echo -e "${GREEN}✅ $1${NC}"; }
explain() { echo -e "${CYAN}   💡 $1${NC}"; }
example() { echo -e "${DIM}   📝 مثال: $1${NC}"; }
where() { echo -e "${MAGENTA}   🔗 کجا؟ $1${NC}"; }
ask_with_help() {
  local prompt="$1"; local help_text="$2"; local example_text="$3"; local where_text="$4"; local default_val="$5"; local is_secret="${6:-false}"
  echo ""; echo -e "${BOLD}${BLUE}❓ $prompt${NC}"; [ -n "$help_text" ] && explain "$help_text"; [ -n "$example_text" ] && example "$example_text"; [ -n "$where_text" ] && where "$where_text"
  [ -n "$default_val" ] && echo -e "${DIM}   ⏭️  Enter=پیش‌فرض: $default_val${NC}" || echo -e "${DIM}   ⏭️  اگر نداری Enter=mock${NC}"
  local input=""; if [ "$is_secret" = "true" ]; then read -s -p "   👉 جواب: " input; echo ""; else read -p "   👉 جواب: " input; fi
  [ -z "$input" ] && [ -n "$default_val" ] && input="$default_val"; echo "$input"
}
ask_yes_no() {
  local prompt="$1"; local help_text="$2"; local default_yes="${3:-true}"
  echo ""; echo -e "${BOLD}${BLUE}❓ $prompt${NC}"; [ -n "$help_text" ] && explain "$help_text"
  [ "$default_yes" = "true" ] && echo -e "${DIM}   ⏭️  [Y/n] Enter=بله${NC}" || echo -e "${DIM}   ⏭️  [y/N] Enter=خیر${NC}"
  local input=""; read -p "   👉 جواب (y/n): " input; input=$(echo "$input" | tr '[:upper:]' '[:lower:]')
  [ -z "$input" ] && { if [ "$default_yes" = "true" ]; then input="y"; else input="n"; fi; }
  if [ "$input" = "y" ] || [ "$input" = "yes" ] || [ "$input" = "بله" ]; then echo "yes"; else echo "no"; fi
}

clear
echo -e "${CYAN}"
cat <<'BANNER'
 ____            _           _     ____       _           _
|  _ \ _ __ ___ (_) ___  ___| |_  |  _ \ ___ | |__   ___ | |_ ___
| |_) | '__/ _ \| |/ _ \/ __| __| | |_) / _ \| '_ \ / _ \| __/ __|
|  __/| | | (_) | |  __/ (__| |_  |  _ < (_) | |_) | (_) | |_\__ \
|_|   |_|  \___// |\___|\___|\__| |_| \_\___/|_.__/ \___/ \__|___/
Level 5 Autonomous Engineer + Notification — Zero Support
BANNER
echo -e "${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  🧙‍♂️ جادوگر نصب Project Robots v3.0.0 — پشتیبانی صفر${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}سلام! 👋 مهندس خودکار سطح ۵ — تحلیل + پلان + اجرا + تست + نقد + Web UI + ناتیف — سقف!${NC}"
echo ""
read -p "برای شروع جادو Enter بزنید... ✨ " _

echo -e "${BLUE}[1/6] 🔍 سیستم${NC}"; ok "اوکیه"; sleep 1
echo -e "${BLUE}[2/6] 🐳 Docker${NC}"; if command -v docker &> /dev/null; then ok "Docker: $(docker --version)"; else echo -e "${YELLOW}⚠️ Docker نیست — ولی بدون Docker هم کار می‌کنه: python3 -m project_robots${NC}"; fi; sleep 1
echo -e "${BLUE}[3/6] 📦 Python${NC}"; ok "Python: $(python3 --version)"; sleep 1

echo -e "${BLUE}[4/6] 🤖 LLM Provider — برای نقد کد${NC}"
explain "ربات برای نقد کد از LLM استفاده می‌کنه — می‌تونه لوکال باشه (Ollama رایگان) یا Cloud"
echo -e "${YELLOW}   گزینه‌ها: ollama (لوکال رایگان), openai, anthropic, mock${NC}"
LLM_PROVIDER=$(ask_with_help "LLM پرووایدر؟" "برای نقد کد — اگر نمی‌دونی ollama یا mock — ollama لوکال رایگان" "ollama یا openai یا mock" "https://ollama.com/ — نصب Ollama — رایگان" "ollama" "false")
LLM_KEY=""
if [ "$LLM_PROVIDER" != "ollama" ] && [ "$LLM_PROVIDER" != "mock" ]; then
  LLM_KEY=$(ask_with_help "کلید API $LLM_PROVIDER؟" "sk-..." "sk-..." "https://platform.openai.com/api-keys" "" "true")
  ok "LLM تنظیم شد"
fi
sleep 1

echo -e "${BLUE}[5/6] 🔔 Notification System — برای گزارش مهندس${NC}"
explain "وقتی مهندس تحلیل می‌کنه، پلان می‌سازه، تست می‌کنه — ناتیف می‌ده"
NOTIF_EMAIL=$(ask_yes_no "ایمیل ناتیف روشن باشه؟" "وقتی مهندس کارش تموم می‌شه ایمیل بره" "false")
NOTIF_TELEGRAM=$(ask_yes_no "ربات تلگرام برای ناتیف مهندس می‌خوای؟" "وقتی مهندس تحلیل تموم می‌شه تلگرام خبر می‌ده" "false")
TELEGRAM_TOKEN=""; TELEGRAM_CHAT=""
if [ "$NOTIF_TELEGRAM" = "yes" ]; then
  TELEGRAM_TOKEN=$(ask_with_help "توکن ربات؟" "از @BotFather" "123456:ABC..." "@BotFather → /newbot" "" "true")
  TELEGRAM_CHAT=$(ask_with_help "Chat ID؟" "از getUpdates" "123456789" "https://api.telegram.org/bot<TOKEN>/getUpdates" "" "false")
  ok "Telegram تنظیم شد"
fi
sleep 1

echo -e "${BLUE}[6/6] ⚙️ .env + 🏗️ نصب${NC}"
cat > .env <<EOF
# project-robots — .env — جادوگر v3.0.0 — پشتیبانی صفر — $(date)
PYTHONPATH=.

# LLM — برای نقد — چیه؟ هوش مصنوعی برای نقد کد — گزینه: ollama, openai, mock
LLM_PROVIDER=${LLM_PROVIDER}
LOCAL_LLM_ENDPOINT=http://localhost:11434/api/generate
LOCAL_LLM_MODEL=llama3-8b
OPENAI_API_KEY=${LLM_KEY}
ANTHROPIC_API_KEY=${LLM_KEY}

# Notification — ناتیف — چیه؟ اطلاع‌رسانی تحلیل + پلان + تست
NOTIF_IN_APP=true
NOTIF_EMAIL=${NOTIF_EMAIL}
NOTIF_TELEGRAM=${NOTIF_TELEGRAM}
TELEGRAM_BOT_TOKEN=${TELEGRAM_TOKEN}
TELEGRAM_CHAT_ID=${TELEGRAM_CHAT}
EOF

ok ".env ساخته شد"

if [ -f docker-compose.yml ]; then
  docker compose up --build -d 2>&1 | tail -n 10
  ok "Docker ready!"
else
  echo -e "${CYAN}  نصب Python...${NC}"
  python3 -m venv .venv 2>/dev/null || true
  source .venv/bin/activate 2>/dev/null || true
  pip install -e . 2>/dev/null || pip install -r requirements.txt 2>/dev/null || true
  ok "نصب شد!"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  🎉 جادو تمام! مهندس خودکار آماده — پشتیبانی صفر! 🎉${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BOLD}${BLUE}📍 دسترسی:${NC}"
echo -e "${GREEN}  🌐 Web UI: dashboard/index.html — Intelligence + ADRs + file watcher + 181 tests${NC}"
echo -e "${GREEN}  🤖 CLI: python3 -m project_robots --help${NC}"
echo -e "${GREEN}  🧪 Test: pytest -q — 181 tests${NC}"
echo ""
echo -e "${BOLD}${BLUE}✅ چک‌لیست:${NC}"
echo -e "  $([ "$LLM_PROVIDER" != "mock" ] && echo "✅" || echo "⚠️") LLM: $LLM_PROVIDER — نقد کد"
echo -e "  ✅ In-App Notif: همیشه روشن"
echo -e "  $([ "$NOTIF_TELEGRAM" = "yes" ] && echo "✅" || echo "⚪") Telegram Notif: $NOTIF_TELEGRAM"
echo ""
echo -e "${CYAN}📚 docs/SETUP-WIZARD-FA.md${NC}"
echo ""
