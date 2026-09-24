# ARCHITECTURE.md — project-robots — Level 5 Autonomous Software Engineer

## ۵. project-robots — Level 5 Autonomous Software Engineer

### Purpose
Level 5 autonomous software engineer: takes repo, analyzes, plans, implements, tests, with central cache, RAG, local LLM critique, stdlib-only.

### Graph
```mermaid
graph TD
    User --> CLI[CLI<br/>python -m project_robots<br/>or docker]
    CLI --> Orchestrator[Orchestrator<br/>autonomous loop]

    Orchestrator --> Intelligence[intelligence/graph_builder.py<br/>RepoIntelligence<br/>builds graph]
    Intelligence --> RAG[RAG<br/>index.sqlite<br/>central cache]
    Orchestrator --> Planning[planning<br/>cycle-0000...]
    Planning --> ADRs[adrs/<br/>cycle-*.json/md]
    Orchestrator --> Implementation[implementation<br/>edits files]
    Orchestrator --> Testing[testing<br/>pytest --collect-only<br/>HEALTHCHECK]
    Orchestrator --> Critique[critique<br/>local LLM<br/>llama3-8b via 11434]

    subgraph Cache[Central Cache ~/.cache/project-robots]
        GraphCache[graph + intelligence]
        RAGCache[rag/index.sqlite]
        Evidence[evidence/DEC-*.json]
    end

    Intelligence --> Cache
    RAG --> Cache
    Planning --> Cache
    Critique --> Cache

    subgraph Docker[Docker]
        Builder[builder<br/>python:3.11-slim<br/>pip --prefix=/install]
        Runner[runner<br/>python:3.11-slim<br/>USER appuser 1001<br/>HEALTHCHECK pytest]
        Builder --> Runner
    end
```

### Connections
- **CLI → Orchestrator:** Autonomous loop: intelligence → planning → implementation → testing → critique → loop
- **Intelligence → RAG:** Builds repo graph, stores in central cache ~/.cache/project-robots
- **Planning → ADRs:** Generates Architecture Decision Records per cycle
- **Critique → Local LLM:** Via LOCAL_LLM_ENDPOINT http://localhost:11434/api/generate, model llama3-8b
- **Testing → Pytest:** HEALTHCHECK via pytest --collect-only

### Modern Standards Check
- ✅ **Clean Architecture:** intelligence, planning, implementation, testing, critique separated, stdlib-only
- ✅ **Autonomous Loop:** Observe → Orient → Decide → Act (OODA) with ADRs
- ✅ **Local-First:** No secrets, local cache, local LLM optional, no cloud dep
- ✅ **Security:** No hardcoded secrets, no network by default, stdlib-only, no eval
- ✅ **Docker:** Multi-stage builder+runner, USER appuser 1001, HEALTHCHECK, minimal
- ✅ **Testing:** 181 tests, ruff 0, 0 any, 0 console.log, 0 TODO (except intentional marker detection)
- ✅ **Observability:** ADRs, evidence, checks, intelligence latest.json
- ⚠️ **Product Gap:** Needs web UI, LLM-based planning, multi-repo orchestration, real-time file watcher

### Deep Issues Fixed
- **Root Docker:** Fixed to USER appuser
- **Single-Stage:** Fixed to multi-stage
- **.cache Artifacts:** Cleaned, git rm --cached

---


