# Roadmap — project-robots

## Done (v1.0.0)

- [x] Level 1-3: discovery, context, docs, hygiene, plan, check, evidence, report
- [x] Level 4: intelligence (architecture + dependency), impact (speculative execution + risk), critique (senior review)
- [x] Level 5: autonomous loop, learning engine (coupling adjustments, risk weights, critique patterns), evidence store central, learning dir central
- [x] Tests: 181 passed, persistent learning store test, autonomous guard tests
- [x] Fix: 266 utcnow → datetime.now(timezone.utc)
- [x] CI: ruff + pytest
- [x] Docs: README badge+mermaid+quickstart, AGENTS, HANDOFF

## v2 (Explicit, Honest)

### Why v2?
- **Multi-LLM Router**: Currently single local model for critique. v2 will add multi-model router (Ollama/OpenAI/Anthropic) for critique + reflexion. Reason: needs API keys + cost tracking, currently local-only.
- **Distributed Execution**: Currently single-machine autonomous loop. v2: distributed workers via Redis queue. Reason: needs infra + idempotency guard.
- **Golden Benchmarks**: Need real-world repo benchmarks for intelligence accuracy. Reason: requires curated dataset + evaluator.
- **Marketplace**: Robot marketplace for sharing custom robots. Reason: needs auth + registry.

### Next Steps
1. Add multi-LLM router for critique
2. Distributed execution via Redis
3. Golden benchmarks dataset
4. Robot marketplace
