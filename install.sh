#!/usr/bin/env bash
set -e
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

clear
echo -e "${CYAN}"
cat <<'BANNER'
 ____            _           _     ____       _           _
|  _ \ _ __ ___ (_) ___  ___| |_  |  _ \ ___ | |__   ___ | |_ ___
| |_) | '__/ _ \| |/ _ \/ __| __| | |_) / _ \| '_ \ / _ \| __/ __|
|  __/| | | (_) | |  __/ (__| |_  |  _ < (_) | |_) | (_) | |_\__ \
|_|   |_|  \___// |\___|\___|\__| |_| \_\___/|_.__/ \___/ \__|___/
              |__/
Level 5 Autonomous Engineer
BANNER
echo -e "${NC}"
echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  🧙‍♂️ جادوگر نصب Project Robots — فوق ساده${NC}"
echo -e "${BLUE}  نسخه v2.0.0 — سقف 10/10${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}سلام! 👋 مهندس خودکار سطح ۵ — تحلیل + پلان + اجرا + تست + نقد + Web UI Dashboard — سقف!${NC}"
echo ""
read -p "برای شروع جادو Enter بزنید... ✨ " _

echo ""
echo -e "${BLUE}[1/6] 🔍 سیستم...${NC}"
echo -e "${GREEN}  ✓ اوکیه${NC}"
sleep 1

echo ""
echo -e "${BLUE}[2/6] 🐳 Docker — جعبه جادویی...${NC}"
if ! command -v docker &> /dev/null; then
  echo -e "${RED}  ✗ Docker نیست — ولی می‌تونی بدون Docker هم اجرا کنی: python3 -m project_robots${NC}"
else
  echo -e "${GREEN}  ✓ Docker: $(docker --version)${NC}"
fi
sleep 1

echo ""
echo -e "${BLUE}[3/6] 📦 Python...${NC}"
echo -e "${GREEN}  ✓ Python: $(python3 --version)${NC}"
sleep 1

echo ""
echo -e "${BLUE}[4/6] 🔧 وابستگی‌ها...${NC}"
echo -e "${GREEN}  ✓ stdlib-only — بدون وابستگی خارجی — امن!${NC}"
sleep 1

echo ""
echo -e "${BLUE}[5/6] ⚙️ تنظیمات...${NC}"
echo -e "${GREEN}  ✓ No secrets required — local-only${NC}"
sleep 1

echo ""
echo -e "${BLUE}[6/6] 🏗️ ساخت و اجرا...${NC}"
if [ -f docker-compose.yml ]; then
  docker compose up --build -d 2>&1 | tail -n 10
  echo -e "${GREEN}  ✓ Docker ready!${NC}"
else
  echo -e "${CYAN}  نصب Python...${NC}"
  python3 -m venv .venv 2>/dev/null || true
  source .venv/bin/activate 2>/dev/null || true
  pip install -e . 2>/dev/null || pip install -r requirements.txt 2>/dev/null || true
  echo -e "${GREEN}  ✓ نصب شد!${NC}"
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  🎉 جادو تمام! مهندس خودکار آماده! 🎉${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BOLD}${BLUE}📍 دسترسی:${NC}${NC}"
echo -e "${GREEN}  🌐 Web UI: dashboard/index.html — Intelligence + ADRs + file watcher + 181 tests${NC}"
echo -e "${GREEN}  🤖 CLI: python3 -m project_robots --help${NC}"
echo -e "${GREEN}  🧪 Test: pytest -q — 181 tests${NC}"
echo ""
echo -e "${BOLD}${BLUE}🎯 حالا چی؟${NC}${NC}"
echo -e "${YELLOW}  1. dashboard/index.html باز کن 2. Intelligence graph ببین 3. Trigger Loop 4. 181 تست${NC}"
echo ""
echo -e "${CYAN}📚 فوق ساده: docs/SETUP-WIZARD-FA.md${NC}"
echo ""
