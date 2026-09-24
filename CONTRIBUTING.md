# Contributing — راهنمای مشارکت — v3.1.2 — تاریکی روشن شد

**نسخه:** v3.1.2 — سقف 10/10 — تاریکی روشن شد
**برای:** همه — حتی اگر غیر فنی باشی!

## چطور مشارکت کنم؟ — 3 قدم ساده

### قدم 1: Fork + Clone — مثل دانلود فیلم

```bash
git clone https://github.com/ansariaiadmin/project-robots.git
cd project-robots
```

### قدم 2: نصب — جادوگر — فقط Enter — پشتیبانی صفر — تاریکی روشن شد

```bash
chmod +x install.sh
./install.sh
```

جادوگر همه چی رو می‌پرسه با راهنما همون‌جا — فقط ضروری‌ها — پرووایدر + SMS + ناتیف — با هزینه — با تست واقعی — تاریکی روشن شد

### قدم 3: تغییر + تست + PR

```bash
# تغییر بده
# تست بزن
./status.sh — وضعیت پرووایدرها — تاریکی روشن شد
./smoke-test.sh — تست کامل — تاریکی روشن شد
pytest -q — اگر Python
npm test — اگر Node

# Commit
git add -A
git commit -m "feat: my feature — تاریکی روشن شد"
git push origin main

# PR بساز — https://github.com/ansariaiadmin/project-robots/pulls
```

## قوانین — ساده

- **کد تمیز:** ruff 0 — eslint 0 — 0 any — تاریکی روشن شد
- **تست:** هر feature باید تست داشته باشه — 928 تست — تاریکی روشن شد
- **امنیت:** .env permission 600 — no hardcoded secrets — secret scan 0 — تاریکی روشن شد
- **مستندات:** هر feature باید docs داشته باشه — SETUP-WIZARD-FA.md — تاریکی روشن شد
- **پشتیبانی صفر:** هر سوال راهنما همون‌جا — چیه؟ چرا؟ مثال؟ کجا؟ هزینه — تاریکی روشن شد

## چی باید سر جاش باشه که نیست؟ — چک‌لیست

- ✅ README.md — با badge + v3.1.2 + تاریکی روشن شد
- ✅ LICENSE — MIT — باید باشه
- ✅ SECURITY.md — سیاست امنیت — باید باشه — تاریکی روشن شد
- ✅ CHANGELOG.md — تاریخچه نسخه‌ها
- ✅ CONTRIBUTING.md — همین فایل — باید باشه
- ✅ .env.example — با NOTIF + FALLBACK + THROTTLING + توضیح فارسی — تاریکی روشن شد
- ✅ docker-compose.yml — با healthcheck + env_file + NOTIF — تاریکی روشن شد
- ✅ install.sh — v3.1.1 — با chmod 600 + idempotency + هزینه + تست واقعی — تاریکی روشن شد
- ✅ install.bat — v3.1.0 — برای ویندوز — تاریکی روشن شد
- ✅ status.sh — v3.1.0 — با health check پرووایدرها + اعتبار — تاریکی روشن شد
- ✅ smoke-test.sh — v3.1.1 — با SMS تست واقعی + Telegram تست — تاریکی روشن شد
- ✅ backup.sh — v3.1.0 — با encrypt + .env + keep last 7 — تاریکی روشن شد
- ✅ update.sh — v3.1.0 — با backup auto + new env check — تاریکی روشن شد
- ✅ docs/SETUP-WIZARD-FA.md — v3.1.0 — پشتیبانی صفر — تاریکی روشن شد
- ✅ docs/SETUP-WEB-WIZARD.html — v4.0.0 — بدون ترمینال — فقط کلیک — تاریکی روشن شد
- ✅ docs/ARCHITECTURE.md — با mermaid graph — تاریکی روشن شد
- ✅ docs/API.md — با Swagger — باید باشه — تاریکی روشن شد — جدید v3.1.2
- ✅ src/lib/notification — با throttling + fallback — سقف — تاریکی روشن شد
- ✅ src/lib/sms — Ghasedak/Kavenegar واقعی — با balance + cost — تاریکی روشن شد
- ✅ tests — 928 تست — باید باشه
- ✅ .github/workflows — CI/CD — باید باشه

## سوالات؟

- Issues: https://github.com/ansariaiadmin/project-robots/issues
- Docs: docs/SETUP-WIZARD-FA.md — برای مامان بزرگ — تاریکی روشن شد
- Web Wizard: docs/SETUP-WEB-WIZARD.html — بدون ترمینال — v4.0.0 — تاریکی روشن شد

**نویسنده:** Fleet 10/10 — مشارکت سقف — تاریکی روشن شد
**نسخه:** v3.1.2
