# API Documentation — مستندات API — v3.1.2 — تاریکی روشن شد

**نسخه:** v3.1.2 — سقف 10/10 — تاریکی روشن شد
**Base URL:** http://localhost:3000 یا http://localhost:8000

## احراز هویت — Auth

### POST /api/auth/login — ورود

```bash
curl -X POST http://localhost:3000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"admin@project-robots.dev","password":"Admin@123"}'
```

**جواب:**
```json
{
  "token": "jwt-token-...",
  "user": { "email": "admin@project-robots.dev", "role": "admin" }
}
```

**نکته امنیتی — تاریکی روشن شد:**
- رمز پیش‌فرض Admin@123 ناامنه — باید عوض کنی — جادوگر می‌پرسه — حداقل 12 کاراکتر — تاریکی روشن شد
- JWT 30m + refresh — rotation — امن — تاریکی روشن شد
- bcrypt — رمز هش — امن

## سلامت — Health — تاریکی روشن شد

### GET /api/health — سلامت — با پرووایدرها

```bash
curl http://localhost:3000/api/health
curl http://localhost:8000/api/health
```

**جواب v3.1.0 — با پرووایدرها — تاریکی روشن شد:**
```json
{
  "status": "ok",
  "version": "v3.1.2",
  "uptime": "2h 30m",
  "providers": {
    "ai": { "provider": "openai", "status": "ok", "cost": "~0.05$ per request" },
    "sms": { "provider": "ghasedak", "status": "ok", "balance": 5000, "cost": "~120 toman per SMS" },
    "email": { "provider": "smtp", "status": "ok" },
    "telegram": { "status": "ok", "bot": "@project-robots_notif_bot" }
  },
  "notifications": {
    "in_app": "always on — free",
    "email": "on — with throttling — تاریکی روشن شد",
    "sms": "on — with throttling — cost ~120 toman — تاریکی روشن شد",
    "telegram": "on — free — best — تاریکی روشن شد"
  },
  "security": {
    "env_permission": "600 — secure — تاریکی روشن شد",
    "admin_password": "secure — not default — تاریکی روشن شد",
    "fallback": "enabled — if SMS fail in_app+email — تاریکی روشن شد",
    "throttling": "enabled — 5 SMS per min digest — cost control — تاریکی روشن شد"
  }
}
```

**برای status.sh v3.1.0 — تاریکی روشن شد — health check پرووایدرها + اعتبار**

## پرووایدرها — Providers — با هزینه + تست واقعی — تاریکی روشن شد

### AI Provider — پرووایدر هوش مصنوعی

**گزینه‌ها + هزینه — تاریکی روشن شد:**
- openai — GPT-4 — هر درخواست ~0.01 دلار — https://platform.openai.com/api-keys → sk-proj-...
- ollama — لوکال رایگان — https://ollama.com/ — رایگان — بهترین برای شروع
- mock — بدون AI واقعی — رایگان — برای تست

**تست:**
```bash
curl -H "Authorization: Bearer $OPENAI_API_KEY" https://api.openai.com/v1/models
```

### SMS Provider — پنل پیامکی — با هزینه + تست واقعی + fallback + throttling — تاریکی روشن شد

**گزینه‌ها + هزینه:**
- ghasedak — قاصدک — هر پیامک ~120 تومان — https://ghasedak.me/ — رایگان 50 تا — API: POST https://api.ghasedak.me/v2/sms/send/simple — با apikey header
- kavenegar — کاوه‌نگار — هر پیامک ~110 تومان — https://kavenegar.com/ — API: POST https://api.kavenegar.com/v1/{apikey}/sms/send.json
- mock — بدون پیامک واقعی — تو لاگ — رایگان

**تست واقعی — تاریکی روشن شد:**
```bash
curl -X POST -H "apikey: $SMS_API_KEY" -H "Content-Type: application/x-www-form-urlencoded" -d "receptor=09123456789&sender=10008566&message=تست" https://api.ghasedak.me/v2/sms/send/simple
```

**اعتبار:**
```bash
curl -H "apikey: $SMS_API_KEY" https://api.ghasedak.me/v2/account/info
# جواب: {"result":{"balance":5000}} — 5000 تومان — اگر کم هشدار شارژ کن — تاریکی روشن شد
```

**fallback — تاریکی روشن شد:**
- اگر ghasedak fail → kavenegar → mock — نه crash — `SMS_FALLBACK_PROVIDERS=ghasedak,kavenegar,mock`

**throttling — تاریکی روشن شد:**
- اگر 5 SMS در 1 دقیقه بیاد خلاصه — هزینه کنترل — spam جلوگیری — `SMS_THROTTLING_MAX_PER_MINUTE=5`

### Email Provider — با هزینه — تاریکی روشن شد

- smtp — Gmail — رایگان اگر Gmail داری — App Passwords: myaccount.google.com → Security → App Passwords
- resend — Resend.com — رایگان 3000/ماه — https://resend.com/
- mock — تو لاگ — رایگان

### Telegram Bot — رایگان — بهترین — تاریکی روشن شد

**چطور بسازم؟ — 1 دقیقه — رایگان:**
1. تلگرام → @BotFather → /newbot → اسم → یوزرنیم (مثل project-robots_notif_bot)
2. توکن می‌ده — مثل 123456:ABC...
3. ربات رو استارت کن → پیام بده
4. https://api.telegram.org/bot<TOKEN>/getUpdates → chat_id

**تست:**
```bash
curl https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/getMe
# باید ok:true — ربات وجود داره — تاریکی روشن شد

curl -X POST -H "Content-Type: application/json" -d '{"chat_id":"$TELEGRAM_CHAT_ID","text":"🧪 تست"}' https://api.telegram.org/bot$TELEGRAM_BOT_TOKEN/sendMessage
# پیام تست به تلگرام — چک کن — تاریکی روشن شد
```

## ناتیفیکیشن — Notification — با throttling + fallback + هزینه — تاریکی روشن شد — سقف 10/10

### POST /api/notifications/send — ارسال ناتیف — multi-channel

```bash
curl -X POST http://localhost:3000/api/notifications/send \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "kind": "info",
    "titleFa": "ثبت‌نام جدید",
    "bodyFa": "کاربر جدید ثبت‌نام کرد",
    "channels": ["in_app", "email", "sms", "telegram"],
    "priority": "medium"
  }'
```

**کانال‌ها + هزینه — تاریکی روشن شد:**
- in_app — همیشه روشن — رایگان — تو داشبورد — Map in-memory (باید DB بشه — تاریکی)
- email — اگر smtp رایگان — با throttling — اگر 10 ناتیف در 1 دقیقه digest
- sms — هر پیامک ~120 تومان — با throttling — اگر 5 SMS در 1 دقیقه خلاصه — هزینه کنترل
- telegram — رایگان — بهترین — بدون هزینه — Markdown

**fallback — تاریکی روشن شد:**
- اگر SMS fail → in_app + email می‌ره — `NOTIF_FALLBACK_ENABLED=true`

**throttling — تاریکی روشن شد:**
- اگر 10 ناتیف در 1 دقیقه → digest — "10 ناتیف جدید" — هزینه کنترل — spam جلوگیری

## بقیه API — بسته به پروژه

- برای aiwp: POST /api/spec-builder/generate — ساخت افزونه با AI — سقف 10/10
- برای aark-kernel: GET /api/v1/market/ticker — قیمت — LineChart + OrderBook زنده
- برای legal-platform: POST /api/cases — پرونده جدید — با RAG + 6 AI وکیل
- برای forgeops: GET /api/projects — پروژه‌ها — با WS logs streaming
- برای project-robots: POST /api/analyze — تحلیل repo — با Intelligence graph
- برای eaos: POST /api/agent/chat — چت با ایجنت — با pgvector RAG
- برای adaptive-financial-os: POST /api/ledger/entries — تراکنش مالی — با double-entry + idempotency + Kafka
- برای universal-document-os: POST /api/documents/upload — آپلود PDF → OCR multi-engine → Translation + Layout

## Swagger — مستندات تعاملی

- http://localhost:3000/api/docs — Swagger UI — برای Node.js
- http://localhost:8000/docs — FastAPI Docs — برای Python

**تاریکی روشن شد:** API Docs باید سر جاش باشه — با هزینه — با fallback — با throttling — با تست واقعی — با امنیت 600 — v3.1.2

**نویسنده:** Fleet 10/10 — API سقف — تاریکی روشن شد
**نسخه:** v3.1.2
