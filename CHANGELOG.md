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
