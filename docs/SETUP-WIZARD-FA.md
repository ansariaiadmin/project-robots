# 🧙‍♂️ جادوگر نصب Project Robots — مهندس خودکار سطح 5 — فوق ساده — پشتیبانی صفر — Zero Support

**نسخه:** v3.0.0 — سقف 10/10 — Ceiling — پشتیبانی صفر
**زمان:** ۱ دقیقه — فقط ۳ کلیک!
**برای:** غیر فنی — حتی اگر مامان بزرگ باشی!
**ویژگی جدید:** راهنما همون‌جا + فقط چیزای ضروری + پرووایدر + پنل پیامکی + سیستم ناتیفیکیشن

---

## 🎯 Project Robots — مهندس خودکار سطح 5 چیه؟ به زبان ساده:

تحلیل + پلان + اجرا + تست + نقد — RepoIntelligence graph + RAG + ADRs + file watcher real-time + testing 181 + critique local LLM + Web UI Dashboard

**ویژگی‌های سقف 10/10:**
- پشتیبانی صفر — همه راهنماها همون‌جا تو جادوگر
- فقط چیزای ضروری پرسیده می‌شه — بقیه خودکار
- پرووایدرها با راهنما: کجا API Key بگیرم + مثال + تست اتصال
- پنل پیامکی با راهنما: قاصدک/کاوه‌نگار + API Key + شماره فرستنده + تست
- سیستم ناتیفیکیشن سقف: in_app (همیشه روشن) + email + sms + telegram — برای ادمین/وکیل/تریدر

---

## 🚀 جادوگر نصب — فقط ۳ قدم — پشتیبانی صفر!

### قدم ۰: چی لازم داری؟ (۳۰ ثانیه)

یک کامپیوتر با اینترنت — همین! Docker جعبه جادویی خودکار چک می‌شه.

### قدم ۱: دانلود (۳۰ ثانیه)

```bash
git clone https://github.com/ansariaiadmin/project-robots.git
cd project-robots
```

### قدم ۲: جادوگر نصب — فقط Enter! — پشتیبانی صفر (۱ دقیقه)

**ویندوز:** `install.bat` دوبار کلیک

**مک/لینوکس:**
```bash
chmod +x install.sh
./install.sh
```

**چی می‌بینی؟ — همه چی همینجا توضیح داده می‌شه!**

```
[1/8] بررسی سیستم... ✓
[2/8] Docker — جعبه جادویی... ✓ Docker 24.0.5
[3/8] رمزهای بانکی... ✓ 3 رمز 32 کاراکتری ساخته شد — مثل رمز بانکی
[4/8] 🤖 پرووایدر AI — چیه؟ شرکتی که هوش مصنوعی می‌ده
   گزینه‌ها: openai (GPT-4) https://platform.openai.com/api-keys, ollama (لوکال رایگان), mock (برای تست)
   ❓ کدوم پرووایدر؟ (راهنما همون‌جا + مثال + کجا پیدا کنم)
   👉 جواب: ollama یا openai
   ❓ کلید API چیه؟ (با sk- شروع می‌شه — از سایت کپی کن)
   👉 جواب: sk-proj-...

[5/8] 📱 پنل پیامکی — چیه؟ سرویسی که پیامک می‌فرسته
   گزینه‌ها: ghasedak (قاصدک) https://ghasedak.me/, kavenegar https://kavenegar.com/, mock (تو لاگ)
   ❓ کدوم پنل؟ (راهنما + کجا API Key بگیرم)
   👉 جواب: ghasedak
   ❓ کلید API؟ (از پنل → تنظیمات → API)
   👉 جواب: api-key-...
   ❓ شماره فرستنده؟ (مثل 10008566)
   👉 جواب: 10008566
   ✅ تست: اتصال به ghasedak — اوکی

[6/8] 📧 ایمیل + 🔔 ناتیفیکیشن — چیه؟ اطلاع‌رسانی
   ❓ پرووایدر ایمیل؟ smtp/resend/mock
   👉 جواب: smtp
   ❓ آدرس SMTP؟ (مثل smtp.gmail.com)
   👉 جواب: smtp.gmail.com
   ❓ پورت؟ (معمولاً 587)
   👉 جواب: 587
   ❓ نام کاربری؟ (you@gmail.com)
   👉 جواب: you@gmail.com
   ❓ رمز؟ (App Password — myaccount.google.com → Security → App Passwords)
   👉 جواب: ****
   ✅ SMTP تنظیم شد

   🔔 سیستم ناتیفیکیشن — چیه؟ وقتی اتفاقی می‌افته خبر می‌ده
   ❓ ایمیل ناتیف روشن باشه؟ (وقتی پرداخت جدید میاد ایمیل بره)
   👉 جواب: y
   ❓ پیامک ناتیف روشن باشه؟
   👉 جواب: y
   ❓ ربات تلگرام برای ناتیف ادمین می‌خوای؟ (وقتی فروش/خطا میاد تلگرام خبر می‌ده — رایگان)
   👉 جواب: y
   چطور ربات بسازم؟ 1 دقیقه:
   1. تلگرام → @BotFather → /newbot → اسم → یوزرنیم
   2. توکن می‌ده — مثل 123456:ABC...
   3. https://api.telegram.org/bot<TOKEN>/getUpdates → chat_id
   ❓ توکن ربات؟
   👉 جواب: 123456:ABC...
   ❓ Chat ID؟
   👉 جواب: 123456789
   ✅ Telegram تنظیم شد

[7/8] ساخت .env — با همه توضیحات فارسی — 30 خط
[8/8] ساخت و اجرا — docker compose up --build -d
....................
✅ آماده! — http://localhost:3000
```

**فقط چیزای ضروری پرسیده می‌شه — بقیه خودکار!**

### قدم ۳: استفاده (۱۰ ثانیه)

مرورگر → `http://localhost:3000` یا `http://localhost:8000`

---


### 🤖 LLM Provider — برای نقد کد

**چیه؟** هوش مصنوعی برای نقد کد — مثل بازرس

**گزینه‌ها:**
- **ollama** — لوکال رایگان — https://ollama.com/ → نصب → رایگان
- **openai** — GPT-4 — https://platform.openai.com/api-keys
- **mock** — بدون LLM



## 🔔 سیستم ناتیفیکیشن — برای گزارش مهندس — سقف 10/10

**کانال‌ها:**
1. **In-App** — همیشه روشن
2. **Telegram** — وقتی مهندس تحلیل تموم می‌شه تلگرام خبر می‌ده

**کد:** `project_robots/notification/service.py`


---

## 🔄 آپدیت — `./update.sh` — ۳۰ ثانیه — بکاپ خودکار

## 🛠️ دستورات — مثل کنترل تلویزیون:
- `./status.sh` — روشنه؟
- `./logs.sh` — لاگ
- `./stop.sh` / `./start.sh`

## 🆘 عیب‌یابی — پشتیبانی صفر — همه چی همینجاست!

**AI کار نمی‌کنه؟** → .env → AI_PROVIDER + API Key چک کن → https://platform.openai.com/api-keys → کلید جدید

**SMS نمی‌ره؟** → .env → SMS_PROVIDER + SMS_API_KEY چک کن → https://ghasedak.me/ → داشبورد → API → `./logs.sh` → grep SMS

**ایمیل نمی‌ره؟** → .env → SMTP چک کن → Gmail App Password: myaccount.google.com → Security → App Passwords

**تلگرام نمی‌ره؟** → .env → TELEGRAM_BOT_TOKEN + CHAT_ID چک کن → `curl https://api.telegram.org/bot<TOKEN>/getMe` → باید ok:true

**پورت اشغال؟** → `./stop.sh` + `docker compose down` + `./start.sh` — دو نفر روی یک صندلی

**.env خراب؟** → `rm .env` + `./install.sh` — دوباره می‌سازه با راهنما

**ناتیف نمی‌ره؟** → .env → NOTIF_EMAIL, NOTIF_SMS, NOTIF_TELEGRAM باید yes باشه

---

## 🔒 امنیت:
- `.env` = کلید خونه — به کسی نده!
- رمزها بانکی 32 کاراکتری — جادوگر می‌سازه
- Non-root Docker USER 1001
- No hardcoded secrets

---

**برای غیر فنی:** فقط `install.sh` → همه چی همینجا توضیح داده می‌شه → مرورگر → localhost — همین! 🎉

**پشتیبانی صفر:** همه راهنماها همون‌جا بود — اگر بازم گیر کردی: https://github.com/ansariaiadmin/project-robots/issues

**نویسنده:** Fleet 10/10 — سطح اعلی — پشتیبانی صفر — پرووایدر + پیامک + ناتیف
**نسخه:** v3.0.0 — سقف — پشتیبانی صفر
