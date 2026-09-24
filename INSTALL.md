# راهنمای کامل PROJECT_ROBOTS — Level 5 Autonomous Engineer — برای افراد غیر فنی

**نسخه:** v1.0.1 — نصب خودکار + آپدیت خودکار
**برای:** کسی که هیچ دانش فنی ندارد، فقط می‌خواهد استفاده کند

---

## 🎯 این برنامه چیست؟

PROJECT_ROBOTS — Level 5 Autonomous Engineer — مهندس نرم‌افزار خودکار سطح ۵
- **تکنولوژی:** Python 3.11 stdlib only
- **آدرس پیش‌فرض:** CLI: ./project-robots --help
- **نوع:** cli

---

## 🚀 نصب در ۳ قدم (کمتر از ۵ دقیقه)

### قدم ۱: دانلود
```bash
git clone https://github.com/ansariaiadmin/project-robots.git
cd project-robots
```
یا از صفحه Releases فایل zip را دانلود و باز کنید.

### قدم ۲: نصب خودکار (فقط یک دستور!)
```bash
chmod +x install.sh
./install.sh
```
این اسکریپت **خودکار**:
- Docker را چک می‌کند (اگر نیست راهنما می‌دهد)
- فایل `.env` را از `.env.example` می‌سازد و رمزهای تصادفی می‌گذارد
- `docker compose up --build -d` را اجرا می‌کند
- ۳۰ ثانیه صبر می‌کند تا سرویس آماده شود
- آدرس و رمز ورود را نشان می‌دهد

**برای ویندوز:**
```bat
install.bat
```
یا روی `install.sh` با Git Bash دوبار کلیک کنید.

### قدم ۳: استفاده
مرورگر را باز کنید:
```
CLI: ./project-robots --help
```
- ورود: بدون رمز - محلی
- سلامت: pytest --collect-only

**تمام!** 🎉

---

## 🔄 آپدیت (به‌روزرسانی)

هر وقت نسخه جدید آمد:

```bash
./update.sh
```

این اسکریپت:
1. بکاپ خودکار می‌گیرد به `backups/YYYYMMDD-HHMMSS/`
2. آخرین کد را از GitHub می‌گیرد (`git pull`)
3. Docker images را آپدیت می‌کند
4. دوباره می‌سازد و اجرا می‌کند
5. سلامت را چک می‌کند، اگر خراب بود راه بازگردانی نشان می‌دهد

**بازگردانی اگر آپدیت خراب شد:**
```bash
cp backups/20240101-120000/.env .env
docker compose up -d
```

---

## 🛠️ دستورات روزانه

| دستور | توضیح فارسی | توضیح انگلیسی |
|-------|-------------|---------------|
| `./install.sh` | نصب اولیه خودکار | Auto install |
| `./update.sh` | آپدیت به آخرین نسخه | Update to latest |
| `./start.sh` | شروع سرویس | Start |
| `./stop.sh` | توقف سرویس | Stop |
| `./status.sh` | وضعیت + سلامت | Status + health |
| `./logs.sh` | دیدن لاگ‌ها | View logs |
| `./backup.sh` | بکاپ گیری | Backup |

**مثال:**
```bash
./status.sh   # ببین روشن است یا نه
./logs.sh     # اگر خطا داشت لاگ ببین
./stop.sh     # خاموش
./start.sh    # روشن
```

---

## 📚 آموزش کامل بخش‌ها

### ۱. داشبورد اصلی
- آدرس: CLI: ./project-robots --help
- بعد از ورود، منوی اصلی را می‌بینید
- هر بخش یک آیکون دارد، کلیک کنید

### ۲. تنظیمات (.env)
فایل `.env` تمام رمزها و آدرس‌هاست. **دست نزنید مگر لازم باشد!**
- اگر خراب شد: `cp .env.example .env` و دوباره `install.sh`
- رمزها با `openssl rand -base64 32` ساخته می‌شوند

### ۳. Docker چیست؟
Docker یک جعبه است که برنامه را با همه وسایلش اجرا می‌کند، بدون اینکه کامپیوتر شما به هم بریزد.
- `docker compose ps` → ببین چه کانتینرهایی روشن است
- `docker compose logs -f` → لاگ زنده
- `docker compose down` → خاموش
- `docker compose up -d` → روشن

### ۴. بکاپ و بازگردانی
```bash
./backup.sh
# بکاپ در backups/2024.../ ساخته می‌شود
# برای بازگردانی:
cp backups/xxx/.env .env
docker compose up -d
```

### ۵. عیب‌یابی (Troubleshooting)

**مشکل: پورت اشغال است / Port already in use**
```bash
docker compose down
# یا
sudo lsof -i :CLI
# سپس
./start.sh
```

**مشکل: Docker نصب نیست**
- ویندوز/مک: Docker Desktop نصب کن https://docs.docker.com/get-docker/
- لینوکس: `curl -fsSL https://get.docker.com | sh`

**مشکل: .env خراب**
```bash
rm .env
cp .env.example .env
./install.sh
```

**مشکل: سرویس بالا نمی‌آید**
```bash
./logs.sh
# لاگ را بخوان، معمولا رمز یا دیتابیس مشکل دارد
./backup.sh
./stop.sh
./start.sh
```

### ۶. امنیت
- `.env` را به کسی ندهید (رمزها داخلش است)
- فقط `.env.example` را به اشتراک بگذارید
- بکاپ‌ها را جای امن نگه دارید
- آپدیت منظم با `./update.sh`

---

## 🖥️ نصب بدون Docker (برای توسعه‌دهندگان)

اگر Docker نمی‌خواهید:

**Python:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pytest -q
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

**Node:**
```bash
npm install
cp .env.example .env
npm run db:migrate
npm run dev
```

---

## 📦 ورژن‌ها و آپدیت خودکار

- **v1.0.0 / v0.9.0:** نسخه اولیه ۱۰/۱۰ نهایی
- **v1.0.1 / v0.9.1:** نسخه غیرفنی + نصب خودکار + آپدیت خودکار (همین نسخه)

برای نصب نسخه خاص:
```bash
git clone https://github.com/ansariaiadmin/project-robots.git
cd project-robots
git checkout v1.0.1  # یا v0.9.1
./install.sh
```

برای آپدیت به آخرین نسخه:
```bash
./update.sh
# یا دستی:
git pull origin main
./install.sh
```

---

## 🆘 کمک

- مستندات کامل: `README.md`
- راهنمای فنی: `docs/USER_GUIDE_EN.md`
- Handoff: `AGENTS.md` و `ROADMAP.md`
- ایشو باز کن: https://github.com/ansariaiadmin/project-robots/issues

**برای افراد کاملا غیر فنی:** فقط `install.sh` را اجرا کن، بعد مرورگر را باز کن به CLI: ./project-robots --help — همین!

---

**نویسنده:** Fleet 10/10 Final Quality Campaign
**تاریخ:** 2026-09-24
