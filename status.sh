#!/usr/bin/env bash
echo "وضعیت PROJECT_ROBOTS — Level 5 Autonomous Engineer / Status PROJECT_ROBOTS — Level 5 Autonomous Engineer"
echo "========================================"
if [ -f docker-compose.yml ]; then
  docker compose ps
  echo ""
  echo "Health: pytest --collect-only"
  if command -v curl &> /dev/null; then
    echo "Checking health..."
    curl -sf pytest --collect-only 2>&1 | head -n 10 || echo "Health endpoint not responding yet"
    curl -sf http://localhost:3000 2>&1 | head -n 2 || true
    curl -sf http://localhost:8000/api/health 2>&1 | head -n 5 || true
  fi
else
  echo "CLI tool - checking processes"
  ps aux | grep -E "project-robots|python|node" | grep -v grep | head -n 10
  echo "برای تست: pytest -q"
fi
echo ""
echo "URL: CLI: ./project-robots --help"
echo "Logs: ./logs.sh"
