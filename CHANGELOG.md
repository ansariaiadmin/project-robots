## [v1.0.1] - 2026-09-24 - Non-Technical Auto Install + Auto Update Edition

### Added - نصب خودکار برای افراد غیر فنی
- **install.sh**: نصب خودکار تمیز - چک Docker, ساخت .env با رمز تصادفی openssl, docker compose up --build -d, صبر 30s, سلامت چک, نمایش آدرس و رمز ورود
- **update.sh**: آپدیت خودکار - بکاپ به backups/YYYYMMDD-HHMMSS/, git pull origin main, docker compose pull + up --build -d, health check, rollback hint
- **start.sh, stop.sh, status.sh, logs.sh, backup.sh**: دستورات ساده روزانه
- **install.bat, start.bat, stop.bat, status.bat, logs.bat, update.bat, backup.bat**: نسخه ویندوز برای افراد غیر فنی
- **INSTALL.md**: راهنمای کامل فارسی نصب در 3 قدم (<5 دقیقه)
- **docs/USER_GUIDE_FA.md**: آموزش کامل تمام بخش‌ها - داشبورد, تنظیمات .env, Docker چیست, بکاپ, عیب‌یابی, امنیت, ورژن‌ها
- **docs/USER_GUIDE_EN.md**: Full English guide for non-technical
- **README**: بخش جدید "برای افراد غیر فنی / For Non-Technical Users — نصب در 1 دقیقه!" با one-liner

### Fixed
- Clean presentation: حذف cache artifacts, .env فقط .env.example
- Non-technical UX: پیام‌های فارسی + انگلیسی، رنگی، راهنمای قدم به قدم

### Docs
- README badge+mermaid+quickstart+sample output + non-technical section
- INSTALL.md + docs/USER_GUIDE_FA.md + docs/USER_GUIDE_EN.md

# Changelog — project-robots

## [1.0.0] - 2026-09-24

### Added
- Level 5 Autonomous Software Engineer: intelligence, impact, critique, autonomous loop
- 181 tests passing, zero warnings (utcnow fixed to datetime.now(timezone.utc))
- Persistent learning store: save_lesson, load_lessons, get_relevant_lessons with keyword overlap + JSONL append-only
- Evidence store central cache, learning engine central cache
- CI: ruff + pytest + compile + docker healthcheck
- Docs: README badge+mermaid+quickstart+sample output, ROADMAP Done vs v2, AGENTS with 10 agents

### Fixed
- 266 utcnow deprecations fixed across learning.py, adr.py, package.py, intelligence/core.py, etc → datetime.now(timezone.utc)
- Indentation SyntaxError fixed in intelligence modules
- Persistent learning store test: test_lesson_persistence_and_load

### Security
- Secret scan 0, no private key, .env.example minimal (no secrets, local-only)

## [0.9.0] - 2026-09-07
- Previous release with 181 tests but utcnow warnings
