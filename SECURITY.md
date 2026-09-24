# Security Policy — سیاست امنیت — v3.1.2 — تاریکی روشن شد

## Supported Versions — نسخه‌های پشتیبانی شده

| Version | Supported |
|---------|-----------|
| v3.1.x  | ✅ |
| v3.0.x  | ✅ |
| < v3.0  | ❌ |

## Reporting a Vulnerability — گزارش آسیب‌پذیری

**لطفاً آسیب‌پذیری را عمومی نکنید — خصوصی گزارش دهید:**

- Email: security@ansariaiadmin.dev
- GitHub: https://github.com/ansariaiadmin/project-robots/security/advisories/new
- Telegram: @ansariaiadmin — برای فوری

**چی بگم؟**
- توضیح آسیب‌پذیری — چیه؟ چرا خطرناکه؟
- چطور بازتولید کنم؟ — steps to reproduce
- نسخه — کدوم نسخه؟
- تاثیر — چی می‌شه؟

**چی می‌شه بعد؟**
- 24 ساعت — تایید دریافت — "گرفتیم"
- 72 ساعت — بررسی اولیه — "خطرناکه یا نه"
- 7 روز — فیکس — patch
- 14 روز — ریلیز — v3.1.x — با تشکر از شما — Hall of Fame

## Security Best Practices — بهترین روش‌های امنیت — تاریکی روشن شد

### .env — کلید خونه — باید سر جاش باشه
- `.env` permission 600 — فقط خودت می‌تونی بخونی — `chmod 600 .env` — تاریکی روشن شد
- `.env` تو git نیست — `.gitignore` داره — امن
- رمزها بانکی 32 کاراکتری — `openssl rand -base64 32` — جادوگر می‌سازه — امن — تاریکی روشن شد
- No hardcoded secrets — هیچ رمز ثابتی تو کد نیست — همه از .env — secret scan 0

### Docker — امن — تاریکی روشن شد
- Non-root USER 1001 — نه root — امن‌تر
- HEALTHCHECK — هر 30 ثانیه — اگر down restart
- No secrets in image — همه از env_file .env

### Admin — رمز امن — تاریکی روشن شد
- رمز پیش‌فرض Admin@123 ناامنه — باید عوض کنی — جادوگر می‌پرسه — حداقل 12 کاراکتر — حرف بزرگ+کوچک+عدد+علامت
- 2FA — به زودی — v4.0.0

### SMS + Telegram — امن — تاریکی روشن شد
- SMS API Key تو .env — permission 600 — امن
- Telegram Bot Token تو .env — permission 600 — امن — به کسی نده
- Telegram Chat ID خصوصی — به کسی نده

### Backup — encrypt — تاریکی روشن شد
- بکاپ با AES-256 encrypt — `openssl enc -aes-256-cbc` — امن
- کلید encrypt تو .env: BACKUP_ENCRYPTION_KEY — امن نگه دار
- بکاپ شامل .env + DB + کلیدها — همه encrypt

### Notification — throttling + fallback — تاریکی روشن شد
- throttling — اگر 5 SMS در 1 دقیقه خلاصه — هزینه کنترل — spam جلوگیری
- fallback — اگر SMS fail in_app+email — امن

## Hall of Fame — تشکر

از گزارش‌دهندگان تشکر — اسمشون اینجا — با اجازه

## تاریخچه — Changelog

- v3.1.2 — تاریکی روشن شد — logger import + web wizard — امن
- v3.1.1 — تاریکی روشن شد — 18 باگ فیکس — امن
- v3.1.0 — تاریکی روشن شد — 14 تاریکی روشن — امن
- v3.0.0 — پشتیبانی صفر — امن
- v2.0.0 — سقف 10/10 — امن

**نویسنده:** Fleet 10/10 — امنیت سقف — تاریکی روشن شد
**نسخه:** v3.1.2
