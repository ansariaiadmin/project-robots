#!/usr/bin/env bash
echo "لاگ‌های PROJECT_ROBOTS — Level 5 Autonomous Engineer / Logs PROJECT_ROBOTS — Level 5 Autonomous Engineer"
echo "========================================"
if [ -f docker-compose.yml ]; then
  docker compose logs --tail=100 -f
else
  echo "لاگ فایل‌ها:"
  ls -lh logs/ 2>/dev/null || ls -lh *.log 2>/dev/null || echo "لاگ فایل مستقیم وجود ندارد، با pytest -q تست کنید"
  if [ -d .venv ]; then
    echo "برای اجرای دستی با لاگ: source .venv/bin/activate && python -m app.main"
  fi
fi
