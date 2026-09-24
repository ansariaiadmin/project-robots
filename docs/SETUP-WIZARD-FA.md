# 🧙‍♂️ جادوگر نصب Project Robots — Level 5 Autonomous Engineer — فوق ساده!

**نسخه:** v2.0.0 — سقف 10/10 — Ceiling
**زمان:** ۱ دقیقه — فقط ۳ کلیک!
**برای:** غیر فنی — حتی اگر Docker ندونی

---

## 🎯 Project Robots — Level 5 Autonomous Engineer چیه؟ به زبان ساده:

مهندس نرم‌افزار خودکار سطح ۵ — تحلیل + پلان + اجرا + تست + نقد

**ویژگی‌های سقف 10/10:**
RepoIntelligence graph + RAG + ADRs + file watcher real-time + testing 181 + critique local LLM + multi-repo orchestration + Web UI Dashboard — سقف 10/10

---

## 🚀 جادوگر نصب — فقط ۳ قدم!

### قدم ۰: چی لازم داری؟ (۳۰ ثانیه)

یک کامپیوتر با اینترنت — Docker جعبه جادویی — جادوگر چک می‌کنه.

### قدم ۱: دانلود (۳۰ ثانیه)

```bash
git clone https://github.com/ansariaiadmin/project-robots.git
cd project-robots
```
یا zip از Releases → Extract

### قدم ۲: جادوگر نصب — فقط Enter! (۱ دقیقه)

**ویندوز:** `install.bat` دوبار کلیک

**مک/لینوکس:**
```bash
chmod +x install.sh
./install.sh
```

**چی می‌بینی؟**
```
[1/6] بررسی سیستم... ✓
[2/6] Docker... ✓ Docker 24.0.5
[3/6] Git... ✓
[4/6] وابستگی‌ها... ✓ Docker کافیه!
[5/6] تنظیمات — رمز بانکی... ✓ .env ساخته شد
[6/6] ساخت و اجرا — docker compose up --build -d
....................
✓ آماده! — http://localhost:8000 یا dashboard/index.html
```

### قدم ۳: استفاده (۱۰ ثانیه)

مرورگر → `http://localhost:8000 یا dashboard/index.html`

**چی کار کن؟**
1. CLI python -m project_robots یا Web UI dashboard/index.html باز کن 2. Intelligence graph ببین 3. Trigger Loop 4. 181 تست ببین

---

## 🔄 آپدیت — `./update.sh` — ۳۰ ثانیه — بکاپ خودکار

## 🛠️ دستورات — مثل کنترل تلویزیون:
- `./status.sh` — روشنه؟
- `./logs.sh` — لاگ
- `./stop.sh` / `./start.sh`

## 🆘 عیب‌یابی — به زبان ساده:

**پورت اشغال:** `./stop.sh` + `docker compose down` + `./start.sh`

**Docker نیست:** https://docs.docker.com/get-docker/

**.env خراب:** `rm .env` + `cp .env.example .env` + `./install.sh`

**سرویس بالا نمی‌آد:** `./logs.sh`

---

## 🔒 امنیت:
- `.env` کلید خونه — به کسی نده!
- Non-root Docker USER 1001 — نه root
- No hardcoded secrets — env_file
- Secret scan 0

---

**برای غیر فنی:** فقط `install.sh` → مرورگر → http://localhost:8000 یا dashboard/index.html — همین! 🎉

**نویسنده:** Fleet 10/10 — سطح اعلی — نهایت سادگی
**نسخه:** v2.0.0 — سقف
