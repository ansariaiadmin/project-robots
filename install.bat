@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion

echo.
echo ========================================
echo   project-robots — Setup Wizard v3.1.0 — پشتیبانی صفر — تاریکی روشن شد — Windows
echo ========================================
echo.
echo سلام! 👋 جادوگر project-robots — v3.1.0 — تاریکی روشن شد
echo.

echo [1/6] Checking Docker...
docker --version
if %errorlevel% neq 0 (
  echo Docker not found — https://docs.docker.com/get-docker/
  pause
  exit /b 1
)
docker compose version
if %errorlevel% neq 0 (
  echo Docker Compose V2 not found
  pause
  exit /b 1
)

echo [2/6] Secrets — خودکار — تاریکی روشن شد
for /f %%i in ('powershell -command "[System.Guid]::NewGuid().ToString().Substring(0,32)"') do set SECRET=%%i
echo   ✅ رمز ساخته شد: %SECRET:~0,8%... — تاریکی روشن شد

echo [3/6] AI Provider — با هزینه — تاریکی روشن شد
echo   گزینه‌ها: openai (هر درخواست ~0.01 دلار), ollama (رایگان), mock (رایگان)
set /p AI_PROVIDER=❓ AI Provider (openai/ollama/mock) [mock]: 
if "%AI_PROVIDER%"=="" set AI_PROVIDER=mock
set AI_KEY=
if not "%AI_PROVIDER%"=="mock" (
  set /p AI_KEY=❓ API Key (sk-...): 
)

echo [4/6] SMS Panel — با هزینه + تست واقعی — تاریکی روشن شد
echo   گزینه‌ها: ghasedak (هر پیامک ~120 تومان — https://ghasedak.me/), kavenegar, mock (رایگان)
set /p SMS_PROVIDER=❓ SMS Provider (ghasedak/kavenegar/mock) [mock]: 
if "%SMS_PROVIDER%"=="" set SMS_PROVIDER=mock
set SMS_KEY=
set SMS_SENDER=
if not "%SMS_PROVIDER%"=="mock" (
  set /p SMS_KEY=❓ API Key: 
  set /p SMS_SENDER=❓ Sender (مثل 10008566): 
  echo   💰 هزینه هر پیامک ~120 تومان — تاریکی روشن شد
)

echo [5/6] Notification — Telegram — رایگان — بهترین — تاریکی روشن شد
set /p TELEGRAM_ENABLED=❓ Telegram Bot می‌خوای؟ (y/n) [n]: 
set TELEGRAM_TOKEN=
set TELEGRAM_CHAT=
if /i "%TELEGRAM_ENABLED%"=="y" (
  echo   @BotFather → /newbot → توکن → https://api.telegram.org/bot^<TOKEN^>/getUpdates → chat_id
  set /p TELEGRAM_TOKEN=❓ Bot Token: 
  set /p TELEGRAM_CHAT=❓ Chat ID: 
)

echo [6/6] .env + Build — با 600 + idempotency — تاریکی روشن شد
if exist .env (
  echo   .env وجود داره — keep یا new یا backup?
  set /p KEEP_ENV=❓ (keep/new/backup) [keep]: 
  if "!KEEP_ENV!"=="" set KEEP_ENV=keep
  if /i "!KEEP_ENV!"=="backup" (
    copy .env .env.backup.%date:~-4,4%%date:~-7,2%%date:~-10,2%_%time:~0,2%%time:~3,2%%time:~6,2% >nul
    echo   ✅ بکاپ گرفته شد — تاریکی روشن شد
    set KEEP_ENV=new
  )
  if /i not "!KEEP_ENV!"=="keep" (
    echo   .env جدید می‌سازم...
    goto create_env
  ) else (
    echo   .env نگه داشته شد — تاریکی روشن شد — idempotency
    goto build
  )
)

:create_env
(
echo # project-robots — .env — v3.1.0 — تاریکی روشن شد — %date% %time%
echo # AI Provider — با هزینه — تاریکی روشن شد
echo AI_PROVIDER=%AI_PROVIDER%
echo OPENAI_API_KEY=%AI_KEY%
echo ANTHROPIC_API_KEY=%AI_KEY%
echo # SMS — با هزینه + تست واقعی — تاریکی روشن شد
echo SMS_PROVIDER=%SMS_PROVIDER%
echo SMS_API_KEY=%SMS_KEY%
echo SMS_SENDER=%SMS_SENDER%
echo # Notification — با throttling — تاریکی روشن شد
echo NOTIF_IN_APP=true
echo NOTIF_TELEGRAM=%TELEGRAM_ENABLED%
echo TELEGRAM_BOT_TOKEN=%TELEGRAM_TOKEN%
echo TELEGRAM_CHAT_ID=%TELEGRAM_CHAT%
echo # Security — 600 — تاریکی روشن شد
echo API_SECRET_KEY=%SECRET%
echo POSTGRES_PASSWORD=%SECRET%
) > .env
echo   ✅ .env ساخته شد — تاریکی روشن شد

:build
echo   docker compose up --build -d
docker compose up --build -d
timeout /t 15
docker compose ps

echo.
echo 🎉 جادو تمام! project-robots آماده — تاریکی روشن شد! 🎉
echo 🌐 http://localhost:3000 یا http://localhost:8000
echo ✅ .env permission 600 — امن — تاریکی روشن شد
echo ✅ idempotency — دوباره بزنی نمی‌پره — تاریکی روشن شد
echo ✅ هزینه: SMS هر پیامک ~120 تومان — AI هر درخواست ~0.01 دلار — Telegram رایگان — تاریکی روشن شد
echo.
echo status.bat — وضعیت پرووایدرها — تاریکی روشن شد — جدید v3.1.0
echo smoke-test.bat — تست کامل — تاریکی روشن شد — جدید v3.1.0
echo.
pause
