#!/usr/bin/env bash
set -e
echo "شروع PROJECT_ROBOTS — Level 5 Autonomous Engineer / Starting PROJECT_ROBOTS — Level 5 Autonomous Engineer..."
if [ -f docker-compose.yml ]; then
  docker compose up -d
  docker compose ps
  echo "✓ اجرا شد / Started - CLI: ./project-robots --help"
else
  echo "برای CLI: ./project-robots --help یا source .venv/bin/activate && python -m app.main"
  if [ -f package.json ]; then npm run dev; fi
fi
