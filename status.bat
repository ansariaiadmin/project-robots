@echo off
echo 📊 وضعیت project-robots — Status v3.1.0 — تاریکی روشن شد
echo ========================================
docker --version
docker compose ps
echo.
echo 🔑 .env — امنیت — تاریکی روشن شد
if exist .env (
  echo ✅ .env وجود دارد
) else (
  echo ❌ .env نیست — install.bat بزن
)
echo.
echo 🤖 پرووایدرها — تاریکی روشن شد
echo   اگر mock — رایگان — بعداً کلید واقعی بذار
echo   اگر ghasedak/kavenegar — هر پیامک ~120 تومان — اعتبار چک کن
echo   اگر openai — هر درخواست ~0.01 دلار
echo   Telegram — رایگان — بهترین
echo.
echo 🌐 Health
curl -sf http://localhost:3000 >nul 2>&1 && echo ✅ http://localhost:3000 — اوکی || echo ⚠️ http://localhost:3000 — خاموش
curl -sf http://localhost:8000 >nul 2>&1 && echo ✅ http://localhost:8000 — اوکی || echo ⚠️ http://localhost:8000 — خاموش
echo.
pause
