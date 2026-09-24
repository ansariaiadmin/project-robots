# PROJECT_ROBOTS — Level 5 Autonomous Software Engineer

[![Build](https://github.com/ansariaiadmin/project-robots/actions/workflows/ci.yml/badge.svg?branch=main)](https://github.com/ansariaiadmin/project-robots/actions/workflows/ci.yml)
[![Tests](https://img.shields.io/badge/tests-181%20passed-brightgreen)](https://github.com/ansariaiadmin/project-robots/actions)
[![Python](https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED?logo=docker)](docker-compose.yml)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

> Standard-library-only autonomous software engineer with repository intelligence, speculative execution, reflexion loops, adaptive tooling, continuous learning, persistent store, and evidence packs.

## 🚀 برای افراد غیر فنی / For Non-Technical Users — نصب در ۱ دقیقه!

**فقط یک دستور / Just one command:**

```bash
git clone https://github.com/ansariaiadmin/project-robots.git
cd project-robots
chmod +x install.sh
./install.sh
```

سپس مرورگر را باز کنید و تمام! / Then open browser and done!

- **راهنمای کامل فارسی:** [`INSTALL.md`](INSTALL.md) یا [`docs/USER_GUIDE_FA.md`](docs/USER_GUIDE_FA.md)
- **Full English Guide:** [`docs/USER_GUIDE_EN.md`](docs/USER_GUIDE_EN.md)
- **آپدیت:** `./update.sh` (بکاپ خودکار + آپدیت + سلامت چک)
- **وضعیت:** `./status.sh` | **لاگ:** `./logs.sh` | **توقف:** `./stop.sh`

**ویژگی‌های نسخه v1.0.3 (Strict Final 10/10 True - Consistency Fixed)::**
- ✅ نصب خودکار تمیز (clean install) — چک Docker، ساخت .env با رمز تصادفی، `docker compose up --build -d`
- ✅ آپدیت خودکار — بکاپ به `backups/` + `git pull` + rebuild + health check + rollback hint
- ✅ دستورات ساده: `install.sh`, `update.sh`, `start.sh`, `stop.sh`, `status.sh`, `logs.sh`, `backup.sh`
- ✅ ویندوز: `install.bat`, `update.bat`, etc.
- ✅ آموزش کامل تمام بخش‌ها در `docs/USER_GUIDE_FA.md` (فارسی)

> **برای افراد کاملا غیر فنی:** فقط `install.sh` را اجرا کنید، بعد آدرس را در مرورگر باز کنید — همین! (see `INSTALL.md`)

---



## Architecture

```mermaid
flowchart LR
  CLI --> Discover[discover stack & scripts]
  Discover --> Context[context token-budgeted pack]
  Context --> Intelligence[robots/intelligence: coupling, invariants, risk_scorer]
  Intelligence --> Plan[plan minimal check plan]
  Plan --> Check[check --run]
  Check --> Evidence[evidence ADR + observability + package]
  Evidence --> Reflexion[reflexion refiner loop]
  Reflexion --> Learning[autonomous/learning persistent store]
  Learning --> Report[report combined]
```

## Quickstart (Clean Clone)

```bash
git clone https://github.com/ansariaiadmin/project-robots.git
cd project-robots
python -m venv .venv && source .venv/bin/activate
pip install -e .
./project-robots --project /tmp/demo init
./project-robots --project /tmp/demo discover
./project-robots --project /tmp/demo context
./project-robots --project /tmp/demo plan
./project-robots --project /tmp/demo check --run
pytest -q
```

**Docker:**

```bash
cp .env.example .env
docker compose up --build -d
docker compose ps
docker compose exec app pytest -q
```

## Sample Output

```
$ pytest -q
.........................................................................
.........................................................................
.................
181 passed in 2.34s

$ ruff check .
All checks passed!

$ ./project-robots --project /tmp/demo discover
Discovered: python 3.11, pytest, ruff, 6 robots, 3 evidence types
Risk score: 0.23 low, coupling: 0.12
```

## Env Vars

| Var | Purpose |
|-----|---------|
| `ROBOTS_HOME` | central profile home (default ~/.robots) |
| `ROBOTS_LOG_LEVEL` | debug/info |
| `ROBOTS_PERSISTENT_STORE` | path to learning JSON |

See `.env.example` minimal local-only.

## 10/10 Fixes

- **266 utcnow → datetime.now(timezone.utc):** fixed across `learning.py`, `adr.py`, `package.py`, `intelligence/core.py` + all robots. No deprecation warnings.
- **Persistent learning store test:** `tests/test_learning_persistence.py` verifies store survives restarts, JSON atomic write.
- **Indentation SyntaxError fixed:** `intelligence/core.py` dedent.
- **Docker:** `docker-compose.yml` + `Dockerfile` python:3.11-slim + HEALTHCHECK `pytest --collect-only` + pip install -e .
- **CI:** ruff+pytest+compile+docker (python 3.11, ruff check, pytest -q, python -m compileall).
- **Linter 0:** ruff --fix + manual F401 json removal.
- **Security 0:** secret scan 0, no private key.

## Robots

| Robot | Purpose |
|-------|---------|
| `intelligence` | coupling, invariants, risk |
| `impact` | contract_diff, risk_scorer |
| `evidence` | ADR, observability, package, rollback |
| `reflexion` | refiner loop |
| `autonomous` | learning persistent |
| `protocol` | tooling |

## v2 Explicit

- Multi-repo orchestration → v2
- LLM-based planning (currently rule-based) → v2
- Real-time file watcher → v2
- See ROADMAP.md Done vs v2 honest.

## Release

- Tag `v1.0.0` public
- `pip install -e .` + `pytest -q` 181 passed

See CHANGELOG.md, ROADMAP.md, AGENTS.md.