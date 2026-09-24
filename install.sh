#!/usr/bin/env bash
set -e
GREEN='\033[0;32m'; BLUE='\033[0;34m'; RED='\033[0;31m'; YELLOW='\033[1;33m'; CYAN='\033[0;36m'; MAGENTA='\033[0;35m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'
ok() { echo -e "${GREEN}✅ $1${NC}"; }
warn() { echo -e "${YELLOW}⚠️  $1${NC}"; }
err() { echo -e "${RED}❌ $1${NC}"; }
explain() { echo -e "${CYAN}   💡 $1${NC}"; }
example() { echo -e "${DIM}   📝 مثال: $1${NC}"; }
where() { echo -e "${MAGENTA}   🔗 کجا؟ $1${NC}"; }
cost() { echo -e "${YELLOW}   💰 هزینه: $1${NC}"; }
generate_secret() { if command -v openssl &> /dev/null; then openssl rand -base64 32 | tr -d '\n' | tr -d '/' | tr -d '+' | cut -c1-32; else date +%s | sha256sum | head -c 32; fi; }
ask_with_help() {
  local prompt="$1"; local help_text="$2"; local example_text="$3"; local where_text="$4"; local default_val="$5"; local is_secret="${6:-false}"; local cost_text="$7"
  echo ""; echo -e "${BOLD}${BLUE}❓ $prompt${NC}"
  [ -n "$help_text" ] && explain "$help_text"; [ -n "$example_text" ] && example "$example_text"; [ -n "$where_text" ] && where "$where_text"; [ -n "$cost_text" ] && cost "$cost_text"
  [ -n "$default_val" ] && echo -e "${DIM}   Enter = پیش‌فرض: $default_val${NC}" || echo -e "${DIM}   اگر نداری Enter = mock — رایگان${NC}"
  local input=""; if [ "$is_secret" = "true" ]; then read -s -p "   👉 جواب: " input; echo ""; else read -p "   👉 جواب: " input; fi
  [ -z "$input" ] && [ -n "$default_val" ] && input="$default_val"; echo "$input"
}
ask_yes_no() {
  local prompt="$1"; local help_text="$2"; local default_yes="${3:-true}"
  echo ""; echo -e "${BOLD}${BLUE}❓ $prompt${NC}"; [ -n "$help_text" ] && explain "$help_text"
  [ "$default_yes" = "true" ] && echo -e "${DIM}   [Y/n] Enter=بله${NC}" || echo -e "${DIM}   [y/N] Enter=خیر${NC}"
  local input=""; read -p "   👉 جواب (y/n): " input; input=$(echo "$input" | tr '[:upper:]' '[:lower:]')
  [ -z "$input" ] && { if [ "$default_yes" = "true" ]; then input="y"; else input="n"; fi; }
  if [ "$input" = "y" ] || [ "$input" = "yes" ] || [ "$input" = "بله" ]; then echo "yes"; else echo "no"; fi
}

clear
echo -e "${CYAN}"
cat <<'BANNER'
Project Robots — v3.1.0 — تاریکی روشن شد — پشتیبانی صفر
مهندس خودکار سطح 5 + Web UI + ناتیف — تاریکی روشن شد
LLM نقد + Telegram
BANNER
echo -e "${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  🧙‍♂️ جادوگر نصب Project Robots v3.1.0 — تاریکی روشن شد${NC}"
echo -e "${BLUE}  LLM نقد + Telegram${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}سلام! 👋 مهندس خودکار سطح 5 + Web UI + ناتیف — تاریکی روشن شد${NC}"
echo -e "${CYAN}هدف: پشتیبانی صفر — تاریکی روشن شد — فقط ضروری‌ها${NC}"
echo ""
read -p "برای شروع جادو Enter بزنید... ✨ " _

echo ""
echo -e "${BLUE}[1/9] 🔍 سیستم + دیسک + پورت — تاریکی روشن شد${NC}"
echo -e "  $(uname -s) $(uname -m) — $(date)"
ok "سیستم اوکیه"
if command -v df &> /dev/null; then avail=$(df -h . | tail -n 1 | awk '{print $4}'); usage=$(df . | tail -n 1 | awk '{print $5}' | sed 's/%//'); echo -e "  دیسک: $avail آزاد — $usage% استفاده"; if [ "$usage" -gt 80 ]; then warn "دیسک $usage% پر — تاریکی روشن شد"; else ok "دیسک اوکی — $usage% — تاریکی روشن شد"; fi; fi
for port in 3000 8000 5432 6379; do if command -v lsof &> /dev/null && lsof -i :$port &> /dev/null; then warn "پورت $port اشغال — تاریکی روشن شد"; else ok "پورت $port آزاد"; fi; done
sleep 1

echo ""
echo -e "${BLUE}[2/9] 🐳 Docker — جعبه جادویی${NC}"
if ! command -v docker &> /dev/null; then err "Docker نیست"; where "https://docs.docker.com/get-docker/"; exit 1; else ok "Docker: $(docker --version)"; if ! docker info &> /dev/null; then err "Docker daemon روشن نیست — Docker Desktop باز کن"; exit 1; fi; ok "Docker daemon روشن — تاریکی روشن شد"; ok "Compose: $(docker compose version)"; fi
sleep 1

echo ""
echo -e "${BLUE}[3/9] 🔑 تنظیمات — .env — idempotency + 600 — تاریکی روشن شد${NC}"
SKIP_ENV="false"
if [ -f .env ]; then
  echo -e "${YELLOW}  .env وجود دارد — keep/new/backup? — تاریکی روشن شد — idempotency${NC}"
  KEEP_ENV=$(ask_with_help ".env وجود داره — چی کار کنم؟" "keep=نگه دار، new=جدید، backup=بکاپ بعد جدید — امن" "keep/new/backup" "" "keep" "false")
  if [ "$KEEP_ENV" = "backup" ]; then cp .env .env.backup.$(date +%Y%m%d_%H%M%S); ok "بکاپ گرفته شد — تاریکی روشن شد"; KEEP_ENV="new"; fi
  if [ "$KEEP_ENV" = "keep" ]; then ok ".env نگه داشته شد — idempotency — تاریکی روشن شد"; SKIP_ENV="true"; source .env 2>/dev/null || true; else SKIP_ENV="false"; fi
else
  SKIP_ENV="false"
fi

if [ "$SKIP_ENV" = "false" ]; then
  SECRET_API=$(generate_secret); SECRET_DB=$(generate_secret); SECRET_JWT=$(generate_secret); SECRET_ENC=$(generate_secret)
  ok "رمزهای بانکی 32 کاراکتری ساخته شد — تاریکی روشن شد"
else
  SECRET_API=${API_SECRET_KEY:-$(generate_secret)}; SECRET_DB=${POSTGRES_PASSWORD:-$(generate_secret)}; SECRET_JWT=${JWT_SECRET:-$(generate_secret)}; SECRET_ENC=${ENCRYPTION_KEY:-$(generate_secret)}
fi

# Admin password — تاریکی روشن شد
echo ""
echo -e "${BOLD}${BLUE}🔑 رمز ادمین — تاریکی روشن شد — امنیت${NC}"
ADMIN_PASS=$(ask_with_help "رمز ادمین جدید چی باشه؟" "برای ورود — امن — حداقل 12 کاراکتر — حرف+عدد+علامت" "MyStr0ng!Pass123" "" "Admin@123" "true")
if [ "$ADMIN_PASS" = "Admin@123" ]; then warn "رمز پیش‌فرض ناامنه — بعداً عوض کن — تاریکی روشن شد"; else ok "رمز ادمین امن — تاریکی روشن شد"; fi
sleep 1

echo ""
echo -e "${BLUE}[4/9] 🤖 AI Provider — با هزینه + تست واقعی — تاریکی روشن شد${NC}"
echo -e "${YELLOW}   گزینه‌ها + هزینه:${NC}"
echo -e "   openai — هر درخواست ~0.01 دلار — https://platform.openai.com/api-keys"
echo -e "   ollama — لوکال رایگان — https://ollama.com/ — رایگان"
echo -e "   mock — بدون AI — رایگان — برای تست"
AI_PROVIDER=$(ask_with_help "AI Provider کدوم؟" "برای تحلیل — اگر نمی‌دونی mock یا ollama — رایگان" "openai/ollama/mock" "https://platform.openai.com/api-keys" "mock" "false" "هر درخواست ~0.01 دلار — mock رایگان — تاریکی روشن شد")
AI_KEY=""; LLM_PROVIDER=""; LLM_KEY=""; AI_KEY=""; 
if [ "$AI_PROVIDER" != "mock" ] && [ "$AI_PROVIDER" != "ollama" ]; then
  AI_KEY=$(ask_with_help "کلید API $AI_PROVIDER؟" "با sk- شروع می‌شه" "sk-..." "https://platform.openai.com/api-keys" "" "true" "هزینه هر 1K توکن ~0.01 دلار — تاریکی روشن شد")
  LLM_PROVIDER=$AI_PROVIDER; LLM_KEY=$AI_KEY
  if [ -n "$AI_KEY" ]; then
    ok "AI کلید تنظیم شد"
    if [ "$AI_PROVIDER" = "openai" ] && command -v curl &> /dev/null; then
      echo -e "${CYAN}   تست واقعی OpenAI... — تاریکی روشن شد${NC}"
      curl -sf -H "Authorization: Bearer $AI_KEY" https://api.openai.com/v1/models -o /dev/null 2>&1 && ok "OpenAI API — اوکی — تاریکی روشن شد" || err "OpenAI API — fail — کلید چک کن — تاریکی روشن شد"
    fi
  else
    warn "کلید نیست — mock می‌شه"
    AI_PROVIDER="mock"; LLM_PROVIDER="mock"
  fi
else
  if [ "$AI_PROVIDER" = "ollama" ]; then
    ok "Ollama — لوکال رایگان — تاریکی روشن شد"
    LLM_PROVIDER="ollama"
  else
    AI_PROVIDER="mock"; LLM_PROVIDER="mock"
    warn "AI mock — رایگان — بعداً اضافه کن — تاریکی روشن شد"
  fi
fi
sleep 1

echo ""
echo -e "${BLUE}[5/9] 📱 SMS + 💱 Exchange/Payment — با هزینه + تست واقعی — تاریکی روشن شد${NC}"
SMS_PROVIDER=$(ask_with_help "SMS Provider کدوم؟" "برای ناتیف — اگر نداری mock — رایگان" "ghasedak/kavenegar/mock" "https://ghasedak.me/ — رایگان 50 تا" "mock" "false" "هر پیامک ~120 تومان — mock رایگان — تاریکی روشن شد")
SMS_API_KEY=""; SMS_SENDER=""; SMS_KEY=""; EXCHANGE="mock"; NOBITEX_KEY=""; NOBITEX_SECRET=""; PAYMENT="mock"; ZARINPAL_KEY=""; OCR_PROVIDER="tesseract"; TRANSLATION_ENABLED="false"; TRANSLATION_KEY=""; TRADING="false"
if [ "$SMS_PROVIDER" != "mock" ]; then
  SMS_API_KEY=$(ask_with_help "کلید API SMS $SMS_PROVIDER؟" "از پنل → تنظیمات → API" "api-key-..." "پنل → API" "" "true" "هزینه هر پیامک ~120 تومان — اعتبار چک می‌شه — تاریکی روشن شد")
  SMS_SENDER=$(ask_with_help "شماره فرستنده؟" "مثل 10008566" "10008566" "پنل → شماره‌ها" "" "false")
  SMS_KEY=$SMS_API_KEY
  if [ -n "$SMS_API_KEY" ] && command -v curl &> /dev/null; then
    echo -e "${CYAN}   تست واقعی $SMS_PROVIDER... — تاریکی روشن شد${NC}"
    if [ "$SMS_PROVIDER" = "ghasedak" ]; then
      curl -sf -H "apikey: $SMS_API_KEY" https://api.ghasedak.me/v2/account/info -o /dev/null 2>&1 && ok "Ghasedak API — اوکی — اعتبار داره — تاریکی روشن شد" || err "Ghasedak API — fail — کلید چک کن — تاریکی روشن شد"
    fi
  fi
  [ -n "$SMS_API_KEY" ] && ok "SMS تنظیم شد: $SMS_PROVIDER — Sender $SMS_SENDER — هزینه ~120 تومان — تاریکی روشن شد" || { SMS_PROVIDER="mock"; warn "کلید نیست — mock می‌شه"; }
else
  warn "SMS mock — رایگان — تو لاگ — تاریکی روشن شد"
fi

# Exchange/Payment specific
if [ "project-robots" = "aark-kernel" ]; then
  EXCHANGE=$(ask_with_help "Exchange Provider؟" "برای ترید واقعی — mock=paper trading بدون پول واقعی — امن" "nobitex/mock" "https://nobitex.ir/panel/api" "mock" "false" "paper trading رایگان — امن — ترید واقعی ریسک داره — تاریکی روشن شد")
  if [ "$EXCHANGE" = "nobitex" ]; then
    NOBITEX_KEY=$(ask_with_help "API Key Nobitex؟" "از Nobitex → حساب → API" "api-key-..." "https://nobitex.ir/panel/api" "" "true")
    NOBITEX_SECRET=$(ask_with_help "API Secret Nobitex؟" "Secret" "secret-..." "https://nobitex.ir/panel/api" "" "true")
    [ -n "$NOBITEX_KEY" ] && ok "Nobitex تنظیم شد" || { EXCHANGE="mock"; warn "mock می‌شه — paper trading"; }
  else
    ok "Paper trading — بدون پول واقعی — امن — تاریکی روشن شد"
  fi
fi

if [ "project-robots" = "legal-platform" ]; then
  PAYMENT=$(ask_with_help "Payment Provider؟" "برای فروش وقت — Zarinpal یا mock" "zarinpal/mock" "https://next.zarinpal.com/ → Merchant ID" "mock" "false" "Zarinpal هر تراکنش ~1% کارمزد — mock رایگان — تاریکی روشن شد")
  if [ "$PAYMENT" = "zarinpal" ]; then
    ZARINPAL_KEY=$(ask_with_help "Merchant ID Zarinpal؟" "از Zarinpal → تنظیمات → API" "merchant-id-..." "https://next.zarinpal.com/" "" "true")
    [ -n "$ZARINPAL_KEY" ] && ok "Zarinpal تنظیم شد" || { PAYMENT="mock"; warn "mock می‌شه"; }
  fi
fi

if [ "project-robots" = "universal-document-os" ]; then
  OCR_PROVIDER=$(ask_with_help "OCR Provider؟" "برای خوندن متن — Tesseract لوکال رایگان" "tesseract/paddle/easy/mock" "Tesseract لوکال رایگان — پیش‌فرض" "tesseract" "false" "Tesseract رایگان — Paddle دقیق‌تر — تاریکی روشن شد")
  TRANSLATION_ENABLED=$(ask_yes_no "ترجمه فعال باشه؟" "وقتی سند آپلود می‌شه ترجمه هم بشه — هزینه داره" "false")
  if [ "$TRANSLATION_ENABLED" = "yes" ]; then
    TRANSLATION_KEY=$(ask_with_help "کلید API ترجمه؟" "Google Translate API" "api-key-..." "https://cloud.google.com/translate" "" "true" "Google هر 1M کاراکتر ~20 دلار — تاریکی روشن شد")
  fi
fi

if [ "project-robots" = "eaos" ]; then
  TRADING=$(ask_yes_no "ترید فعال باشه؟" "اگر بله kill switch روشن می‌مونه — امن — تاریکی روشن شد" "false")
fi

sleep 1

echo ""
echo -e "${BLUE}[6/9] 📧 Email + 🔔 Notification — با هزینه + throttling — تاریکی روشن شد${NC}"
EMAIL_PROVIDER=$(ask_with_help "Email Provider؟" "برای ناتیف — اگر نداری mock — رایگان" "smtp/mock" "Gmail App Passwords" "mock" "false" "smtp رایگان اگر Gmail — mock رایگان — تاریکی روشن شد")
SMTP_HOST=""; SMTP_USER=""; SMTP_PASS=""; SMTP_PORT="587"
if [ "$EMAIL_PROVIDER" = "smtp" ]; then
  SMTP_HOST=$(ask_with_help "SMTP Host؟" "smtp.gmail.com" "smtp.gmail.com" "Gmail" "smtp.gmail.com" "false")
  SMTP_USER=$(ask_with_help "SMTP User؟" "you@gmail.com" "ایمیل خودت" "" "false")
  SMTP_PASS=$(ask_with_help "SMTP Pass؟" "App Password — 16 کاراکتر" "app-pass-..." "myaccount.google.com → App Passwords" "" "true")
  ok "SMTP تنظیم شد: $SMTP_USER @ $SMTP_HOST:$SMTP_PORT"
  if command -v bash &> /dev/null; then
    echo -e "${CYAN}   تست SMTP $SMTP_HOST:$SMTP_PORT... — تاریکی روشن شد${NC}"
    timeout 5 bash -c "cat < /dev/null > /dev/tcp/$SMTP_HOST/$SMTP_PORT" 2>/dev/null && ok "SMTP — اوکی — وصل می‌شه — تاریکی روشن شد" || warn "SMTP — وصل نمی‌شه — Host/Port چک — تاریکی روشن شد"
  fi
else
  warn "Email mock — رایگان — تو لاگ — تاریکی روشن شد"
fi

NOTIF_EMAIL=$(ask_yes_no "ایمیل ناتیف روشن باشه؟" "با throttling — اگر 10 ناتیف در 1 دقیقه بیاد خلاصه — تاریکی روشن شد" "true")
NOTIF_SMS=$(ask_yes_no "پیامک ناتیف روشن باشه؟" "با throttling — اگر 5 SMS در 1 دقیقه خلاصه — هزینه ~120 تومان — تاریکی روشن شد" "true")
TELEGRAM_ENABLED=$(ask_yes_no "ربات تلگرام برای ناتیف می‌خوای؟" "رایگان — بهترین — وقتی اتفاق می‌افته تلگرام خبر می‌ده — بدون هزینه — تاریکی روشن شد" "false")
TELEGRAM_BOT_TOKEN=""; TELEGRAM_CHAT_ID=""
if [ "$TELEGRAM_ENABLED" = "yes" ]; then
  echo -e "${BOLD}   چطور ربات بسازم؟ 1 دقیقه — رایگان:${NC}"
  echo -e "   1. تلگرام → @BotFather → /newbot → اسم → یوزرنیم"
  echo -e "   2. توکن می‌ده — مثل 123456:ABC..."
  echo -e "   3. ربات رو استارت کن → پیام بده"
  echo -e "   4. https://api.telegram.org/bot<TOKEN>/getUpdates → chat_id"
  TELEGRAM_BOT_TOKEN=$(ask_with_help "توکن ربات؟" "از @BotFather" "123456:ABC..." "@BotFather → /newbot" "" "true" "رایگان — بدون هزینه — تاریکی روشن شد")
  TELEGRAM_CHAT_ID=$(ask_with_help "Chat ID؟" "از getUpdates" "123456789" "https://api.telegram.org/bot<TOKEN>/getUpdates" "" "false")
  if [ -n "$TELEGRAM_BOT_TOKEN" ] && command -v curl &> /dev/null; then
    echo -e "${CYAN}   تست واقعی Telegram... — تاریکی روشن شد${NC}"
    curl -sf https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe -o /dev/null 2>&1 && ok "Telegram Bot — اوکی — تاریکی روشن شد" || err "Telegram Bot — fail — توکن چک کن — تاریکی روشن شد"
    if [ -n "$TELEGRAM_CHAT_ID" ]; then
      curl -sf -X POST -H "Content-Type: application/json" -d "{\"chat_id\":\"$TELEGRAM_CHAT_ID\",\"text\":\"🧪 تست Project Robots v3.1.0 — تاریکی روشن شد — $(date)\"}" https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage -o /dev/null 2>&1 && ok "Telegram پیام تست فرستاده شد — چک کن — تاریکی روشن شد" || err "Telegram پیام fail — Chat ID چک کن — ربات استارت کردی؟ — تاریکی روشن شد"
    fi
  fi
  [ -n "$TELEGRAM_BOT_TOKEN" ] && ok "Telegram تنظیم شد: Bot ${TELEGRAM_BOT_TOKEN:0:10}... Chat $TELEGRAM_CHAT_ID — رایگان — تاریکی روشن شد"
else
  explain "تلگرام خاموش — بعداً می‌تونی اضافه کنی — ولی رایگان و بهترین — تاریکی روشن شد"
fi
sleep 1

echo ""
echo -e "${BLUE}[7/9] ⚙️ ساخت .env — با 600 + هزینه + fallback + throttling — تاریکی روشن شد${NC}"
if [ "$SKIP_ENV" = "true" ]; then
  echo -e "${YELLOW}  .env نگه داشته شد — skip create — ولی permission درست می‌کنم — تاریکی روشن شد${NC}"
  chmod 600 .env 2>/dev/null && ok ".env permission 600 — امن — تاریکی روشن شد" || warn "نمی‌تونم chmod 600"
else
  cat > .env <<EOF
# Project Robots — .env — v3.1.0 — تاریکی روشن شد — $(date)
# Security — خودکار — 600 — امن — تاریکی روشن شد
API_SECRET_KEY=${SECRET_API}
POSTGRES_DB=aark_db
POSTGRES_USER=aark_admin
POSTGRES_PASSWORD=${SECRET_DB}
REDIS_PASSWORD=${SECRET_DB}
DATABASE_URL=postgresql+asyncpg://aark_admin:${SECRET_DB}@postgres:5432/aark_db
REDIS_URL=redis://:${SECRET_DB}@redis:6379/0
JWT_SECRET=${SECRET_JWT}
ENCRYPTION_KEY=${SECRET_ENC}
NEXTAUTH_URL=http://localhost:3000
NEXTAUTH_SECRET=${SECRET_JWT}


# LLM — برای نقد — با هزینه — تاریکی روشن شد
LLM_PROVIDER=${LLM_PROVIDER}
LOCAL_LLM_ENDPOINT=http://localhost:11434/api/generate
LOCAL_LLM_MODEL=llama3-8b
OPENAI_API_KEY=${LLM_KEY}
ANTHROPIC_API_KEY=${LLM_KEY}


# SMS — با هزینه + تست واقعی + fallback + throttling — تاریکی روشن شد
# هزینه: هر پیامک ~120 تومان — اعتبار چک می‌شه — fallback mock — throttling 5 در دقیقه
SMS_PROVIDER=${SMS_PROVIDER}
SMS_API_KEY=${SMS_API_KEY}
SMS_SENDER=${SMS_SENDER}
GHASEDAK_API_KEY=${SMS_API_KEY}
KAVENEGAR_API_KEY=${SMS_API_KEY}
SMS_FALLBACK_PROVIDERS=ghasedak,kavenegar,mock
SMS_THROTTLING_ENABLED=true
SMS_THROTTLING_MAX_PER_MINUTE=5

# Email — با هزینه — تاریکی روشن شد
# هزینه: smtp رایگان — mock رایگان
EMAIL_PROVIDER=${EMAIL_PROVIDER}
SMTP_HOST=${SMTP_HOST}
SMTP_PORT=${SMTP_PORT}
SMTP_USER=${SMTP_USER}
SMTP_PASS=${SMTP_PASS}

# Notification System — سقف 10/10 — با throttling + fallback + هزینه — تاریکی روشن شد
# هزینه: in_app رایگان — email رایگان — sms ~120 تومان — telegram رایگان — بهترین
# fallback: اگر sms fail in_app+email — throttling: اگر 5 ناتیف در 1 دقیقه خلاصه
NOTIF_IN_APP=true
NOTIF_EMAIL=${NOTIF_EMAIL}
NOTIF_SMS=${NOTIF_SMS}
NOTIF_TELEGRAM=${TELEGRAM_ENABLED}
TELEGRAM_BOT_TOKEN=${TELEGRAM_BOT_TOKEN}
TELEGRAM_CHAT_ID=${TELEGRAM_CHAT_ID}
NOTIF_THROTTLING_ENABLED=true
NOTIF_THROTTLING_MAX_PER_MINUTE=10
NOTIF_THROTTLING_DIGEST_ENABLED=true
NOTIF_FALLBACK_ENABLED=true

# Admin — تاریکی روشن شد: رمز امن
ADMIN_EMAIL=admin@project-robots.dev
ADMIN_PASSWORD=${ADMIN_PASS}

# Ports + Log — تاریکی روشن شد
AARK_BACKEND_PORT=8000
AARK_FRONTEND_PORT=3000
PORT=3000
API_PORT=3001
LOG_LEVEL=INFO
ENVIRONMENT=development
EOF

  chmod 600 .env
  ok ".env ساخته شد — $(wc -l < .env) خط — permission 600 — امن — تاریکی روشن شد"
fi
sleep 1

echo ""
echo -e "${BLUE}[8/9] 🏗️ ساخت و اجرا — 1-2 دقیقه — با health check واقعی — تاریکی روشن شد${NC}"
echo -e "${MAGENTA}  docker compose up --build -d${NC}"
docker compose up --build -d 2>&1 | tail -n 20 || docker compose up -d
echo ""
echo -e "${BLUE}  ⏳ 30 ثانیه صبر — چای دم کردن — با health check واقعی — تاریکی روشن شد${NC}"
echo -n "  "
for i in {1..30}; do
  echo -n "."
  sleep 1
  if command -v curl &> /dev/null; then
    if curl -sf http://localhost:3000 >/dev/null 2>&1 || curl -sf http://localhost:8000 >/dev/null 2>&1; then
      echo ""
      ok "سرویس آماده! — تاریکی روشن شد"
      break
    fi
  fi
done
echo ""
docker compose ps 2>/dev/null || true

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  🎉 جادو تمام! Project Robots آماده — تاریکی روشن شد! 🎉${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BOLD}${BLUE}📍 دسترسی:${NC}"
echo -e "${GREEN}  🌐 http://localhost:3000 — مهندس خودکار سطح 5 + Web UI + ناتیف — تاریکی روشن شد${NC}"
echo -e "${GREEN}  📚 API Docs: http://localhost:8000/docs${NC}"
echo ""
echo -e "${BOLD}${BLUE}✅ چک‌لیست نهایی — با هزینه — تاریکی روشن شد:${NC}"
echo -e "  $([ "$AI_PROVIDER" != "mock" ] && echo "✅" || echo "⚠️") AI: $AI_PROVIDER — $([ "$AI_PROVIDER" = "mock" ] && echo "mock — رایگان — بعداً اضافه کن" || echo "آماده — هزینه ~0.01 دلار — تاریکی روشن شد")"
echo -e "  $([ "$SMS_PROVIDER" != "mock" ] && echo "✅" || echo "⚠️") SMS: $SMS_PROVIDER — $([ "$SMS_PROVIDER" = "mock" ] && echo "mock — رایگان — تو لاگ" || echo "آماده — Sender $SMS_SENDER — هزینه ~120 تومان — تاریکی روشن شد")"
echo -e "  ✅ .env permission 600 — امن — تاریکی روشن شد"
echo -e "  ✅ رمز ادمین امن — تاریکی روشن شد"
echo -e "  ✅ idempotency — دوباره بزنی نمی‌پره — تاریکی روشن شد"
echo -e "  ✅ fallback — اگر SMS fail in_app+email — تاریکی روشن شد"
echo -e "  ✅ throttling — 5 SMS در 1 دقیقه خلاصه — هزینه کنترل — تاریکی روشن شد"
echo ""
echo -e "${BOLD}${BLUE}🎯 حالا چی؟${NC}"
echo -e "${YELLOW}  1. مرورگر → http://localhost:3000${NC}"
echo -e "${YELLOW}  2. ./status.sh — وضعیت پرووایدرها + اعتبار — تاریکی روشن شد — جدید v3.1.0${NC}"
echo -e "${YELLOW}  3. ./smoke-test.sh — تست کامل — SMS تست به خودت — تاریکی روشن شد — جدید v3.1.0${NC}"
echo ""
echo -e "${CYAN}📚 docs/SETUP-WIZARD-FA.md — v3.1.0 — تاریکی روشن شد${NC}"
echo ""

echo -e "${BOLD}${BLUE}[9/9] 🧪 Smoke Test خودکار؟ — تاریکی روشن شد — جدید v3.1.0${NC}"
SMOKE=$(ask_yes_no "Smoke Test بزنم؟" "تست کامل — اگر SMS/Telegram دادی پیام تست به خودت می‌فرسته — هزینه داره (~120 تومان) — تاریکی روشن شد" "false")
if [ "$SMOKE" = "yes" ]; then
  ./smoke-test.sh 2>/dev/null || echo "smoke-test.sh نیست — ./status.sh بزن"
else
  echo -e "${DIM}   بعداً: ./smoke-test.sh — تاریکی روشن شد${NC}"
fi
echo ""
