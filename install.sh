#!/usr/bin/env bash
set -e
# Colors
GREEN='\033[0;32m'
BLUE='\033[0;34m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}========================================${NC}"
echo -e "${BLUE}  PROJECT_ROBOTS — Level 5 Autonomous Engineer${NC}"
echo -e "${BLUE}  نصب خودکار - Auto Installer v1.0.2${NC}"
echo -e "${BLUE}  مهندس نرم‌افزار خودکار سطح ۵${NC}"
echo -e "${BLUE}========================================${NC}"
echo ""
echo -e "${YELLOW}برای افراد غیر فنی - فقط Enter بزنید تا نصب خودکار شروع شود${NC}"
echo -e "${YELLOW}For non-technical users - just press Enter to start auto install${NC}"
echo ""
read -p "برای ادامه Enter بزنید / Press Enter to continue..." _

# Check OS
echo -e "${BLUE}[1/6] بررسی سیستم / Checking system...${NC}"
uname -a
echo ""

# Check Docker (for web types)
if [ "cli" = "web" ]; then
  echo -e "${BLUE}[2/6] بررسی Docker / Checking Docker...${NC}"
  if ! command -v docker &> /dev/null; then
    echo -e "${RED}Docker نصب نیست / Docker not found${NC}"
    echo "لطفا Docker را نصب کنید: https://docs.docker.com/get-docker/"
    echo "Please install Docker: https://docs.docker.com/get-docker/"
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
      echo "در حال تلاش نصب خودکار Docker / Trying auto install..."
      curl -fsSL https://get.docker.com | sh
      sudo usermod -aG docker $USER || true
      echo -e "${YELLOW}لطفا دوباره لاگین کنید و دوباره نصب را اجرا کنید / Please re-login and run again${NC}"
    fi
    exit 1
  else
    echo -e "${GREEN}✓ Docker نصب است / Docker found: $(docker --version)${NC}"
  fi

  if ! docker compose version &> /dev/null; then
    echo -e "${RED}Docker Compose V2 نصب نیست / Docker Compose not found${NC}"
    echo "لطفا Docker Desktop یا Compose V2 نصب کنید"
    exit 1
  else
    echo -e "${GREEN}✓ Docker Compose: $(docker compose version)${NC}"
  fi
  echo ""
fi

# Check Git
echo -e "${BLUE}[3/6] بررسی Git / Checking Git...${NC}"
if ! command -v git &> /dev/null; then
  echo -e "${RED}Git نصب نیست / Git not found - لطفا نصب کنید${NC}"
  exit 1
fi
echo -e "${GREEN}✓ Git: $(git --version)${NC}"
echo ""

# Check Python/Node based on stack
echo -e "${BLUE}[4/6] بررسی وابستگی‌ها / Checking dependencies...${NC}"
if [[ "Python 3.11 stdlib only" == *"Python"* ]]; then
  if command -v python3 &> /dev/null; then
    echo -e "${GREEN}✓ Python: $(python3 --version)${NC}"
  else
    echo -e "${YELLOW}Python3 یافت نشد ولی Docker کافی است / Python not found but Docker is enough${NC}"
  fi
fi
if [[ "Python 3.11 stdlib only" == *"Node"* ]] || [[ "Python 3.11 stdlib only" == *"Next"* ]] || [[ "Python 3.11 stdlib only" == *"Nest"* ]]; then
  if command -v node &> /dev/null; then
    echo -e "${GREEN}✓ Node: $(node --version)${NC}"
  else
    echo -e "${YELLOW}Node یافت نشد ولی Docker کافی است / Node not found but Docker is enough${NC}"
  fi
fi
echo ""

# Generate .env
echo -e "${BLUE}[5/6] ساخت فایل تنظیمات / Creating config...${NC}"
if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    echo -e "${GREEN}کپی .env.example به .env / Copying .env.example to .env${NC}"
    cp .env.example .env
    # Generate secrets
    if command -v openssl &> /dev/null; then
      SECRET=$(openssl rand -base64 32 2>/dev/null | tr -d '\n' | tr -d '/' | cut -c1-32)
      SECRET2=$(openssl rand -base64 32 2>/dev/null | tr -d '\n' | tr -d '/' | cut -c1-32)
      # Replace common placeholders
      if [[ "$OSTYPE" == "darwin"* ]]; then
        sed -i '' "s/change-me-openssl-rand-base64-32/$SECRET/g" .env 2>/dev/null || true
        sed -i '' "s/change-me-32-byte-base64/$SECRET/g" .env 2>/dev/null || true
        sed -i '' "s/change-me/$SECRET/g" .env 2>/dev/null || true
      else
        sed -i "s/change-me-openssl-rand-base64-32/$SECRET/g" .env 2>/dev/null || true
        sed -i "s/change-me-32-byte-base64/$SECRET2/g" .env 2>/dev/null || true
        sed -i "s/change-me/$SECRET/g" .env 2>/dev/null || true
      fi
      echo -e "${GREEN}✓ رمزهای تصادفی ساخته شد / Random secrets generated${NC}"
    else
      echo -e "${YELLOW}openssl یافت نشد، رمزها را دستی عوض کنید / openssl not found, change secrets manually${NC}"
    fi
  else
    echo -e "${YELLOW}.env.example وجود ندارد، .env خالی می‌سازیم / .env.example not found, creating empty .env${NC}"
    touch .env
  fi
  echo -e "${GREEN}✓ فایل .env ساخته شد / .env created - لطفا آن را ویرایش کنید اگر نیاز است${NC}"
else
  echo -e "${BLUE}.env از قبل وجود دارد / .env already exists, skipping${NC}"
fi
echo ""

# Build and start
echo -e "${BLUE}[6/6] ساخت و اجرا / Building and starting...${NC}"
if [ "cli" = "web" ]; then
  if [ -f docker-compose.yml ]; then
    echo "docker compose up --build -d"
    docker compose up --build -d
    echo ""
    echo -e "${BLUE}صبر برای آماده شدن / Waiting to be ready (30s)...${NC}"
    for i in {1..30}; do
      echo -n "."
      sleep 2
      # Check health if curl exists
      if command -v curl &> /dev/null; then
        if curl -sf pytest --collect-only >/dev/null 2>&1 || curl -sf http://localhost:3000 >/dev/null 2>&1 || curl -sf http://localhost:8000 >/dev/null 2>&1 || curl -sf http://localhost:8080 >/dev/null 2>&1; then
          echo ""
          echo -e "${GREEN}✓ سرویس آماده است / Service ready!${NC}"
          break
        fi
      fi
    done
    echo ""
    docker compose ps
  else
    echo -e "${YELLOW}docker-compose.yml یافت نشد / not found, trying npm/pip${NC}"
    if [ -f package.json ]; then
      npm install
      npm run build || true
      echo "برای اجرا: npm run dev / To run: npm run dev"
    elif [ -f requirements.txt ]; then
      python3 -m venv .venv || true
      source .venv/bin/activate 2>/dev/null || true
      pip install -r requirements.txt
      echo "برای اجرا: uvicorn app.main:app --reload / To run: uvicorn..."
    fi
  fi
else
  # CLI type
  if [ -f requirements.txt ]; then
    echo "نصب Python وابستگی‌ها / Installing Python deps..."
    python3 -m venv .venv 2>/dev/null || true
    source .venv/bin/activate 2>/dev/null || true
    pip install -e . 2>/dev/null || pip install -r requirements.txt
    echo -e "${GREEN}✓ نصب شد / Installed${NC}"
    echo "برای تست: pytest -q / To test: pytest -q"
    echo "برای راهنما: ./project-robots --help"
  fi
fi

echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}✓ نصب تمام شد! / Installation Complete! 🎉${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
echo -e "${BLUE}اطلاعات دسترسی / Access Info:${NC}"
echo -e "  آدرس / URL: CLI: ./project-robots --help"
echo -e "  ورود / Login: بدون رمز - محلی"
echo -e "  سلامت / Health: pytest --collect-only"
echo ""
echo -e "${BLUE}دستورات مفید / Useful Commands:${NC}"
echo -e "  ./status.sh  - وضعیت / Status"
echo -e "  ./logs.sh    - لاگ‌ها / Logs"
echo -e "  ./stop.sh    - توقف / Stop"
echo -e "  ./start.sh   - شروع / Start"
echo -e "  ./update.sh  - آپدیت / Update"
echo -e "  ./backup.sh  - بکاپ / Backup"
echo ""
echo -e "${YELLOW}مستندات کامل / Full docs: ./docs/USER_GUIDE_FA.md${NC}"
echo ""
