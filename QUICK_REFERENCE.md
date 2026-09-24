# PROJECT_ROBOTS — Quick Reference Card

## Commands (14 Total)

| Command | Purpose | Key Flags |
|---------|---------|-----------|
| `discover` | Detect stack, scripts, file shape | — |
| `context` | Token-budgeted context pack | `--task`, `--budget` |
| `docs` | Check docs, links, duplicates | — |
| `hygiene` | Conflicts, secrets, generated files | — |
| `clean-plan` | List cleanup candidates (never deletes) | — |
| `plan` | Minimal validation plan | `--full`, `--browser` |
| `check` | Execute check plan | `--full`, `--browser`, `--run` |
| `evidence` | Verify fresh source-bound evidence | — |
| `report` | Combined project report | `--task`, `--budget` |
| `init` | Create central profile | `--force` |
| **`intelligence`** | Architecture & dependency analysis | — |
| **`impact`** | Speculative impact & risk score | — |
| **`critique`** | Senior-engineer plan review | — |
| **`autonomous`** | Continuous sense-plan-act-learn | `--mode`, `--issue`, `--max-cycles`, `--interval` |

## Autonomous Modes

```bash
# One-shot
./project-robots --project /path/to/proj autonomous --mode oneshot --issue "refactor auth"

# Continuous (runs cycles until queue empty or max-cycles)
./project-robots --project /path/to/proj autonomous --mode continuous --max-cycles 50 --interval 300 --issue "tech debt" --issue "security"
```

## Risk Score Thresholds

| Score | Decision |
|-------|----------|
| < 0.15 | Auto-apply |
| 0.15–0.30 | Fast-track review |
| 0.30–0.50 | Full review |
| > 0.50 | Reject |

Risk = 0.35×reachability + 0.25×coupling + 0.20×mutation_survival + 0.15×contract_breakage + 0.05×perf_regression

## Critique Heuristics (10)

1. Root cause addressed?
2. Abstraction level correct?
3. Error surface narrowed?
4. No temporal coupling?
5. Migration path for dependents?
6. Observability added?
7. Performance budget respected?
8. ADR quality sufficient?
9. Architectural style consistent?
10. Security implications handled?

## Tool Selection

| Finding | Tool |
|---------|------|
| Cross-cutting (logging, retry, auth) | Semantic patch (comby) |
| Structural refactor (extract, rename) | AST rewrite (libcst/ruff) |
| Concurrency/state | Model checking (TLA+/Alloy) |
| API/contract | Contract tester + shim |
| Algorithm correctness | Property testing (Hypothesis) |
| Performance | Microbenchmarks |

## Evidence Package (per change)

- **ADR** — Context, decision, alternatives, consequences
- **Impact Analysis** — Blast radius, risk score, coupling
- **Verification Plan** — Mutation, property, contract tests
- **Observability** — Prometheus metrics, OTEL traces, logs, alerts
- **Rollback** — Feature flag / canary / blue-green + SLO triggers
- **Signed** — SHA256 fingerprint + signature

## Config Hierarchy

1. `profiles/universal.json` (defaults)
2. `profiles/<project>-<hash>.json` (central)
3. `.project-robots.json` (project-local, highest priority)

## Key Files

| File | Purpose |
|------|---------|
| `project_robots.py` | CLI entry + dispatch |
| `robots/common.py` | Git, config, cache, source_state |
| `robots/protocol.py` | Robot protocol + registry |
| `robots/intelligence/core.py` | RepositoryIntelligence model |
| `robots/impact/risk_scorer.py` | RiskScore + thresholds |
| `robots/reflexion/critic.py` | 10 heuristic checks |
| `robots/autonomous/loop.py` | Sense→Plan→Critique→Act→Learn |
| `robots/evidence/package.py` | EvidencePackage + ADR + Observability + Rollback |

## Quick Test

```bash
cd /home/ai/Desktop/work/PROJECT_ROBOTS
.venv/bin/python -m pytest tests/test_robots.py -v
./project-robots --project . discover
./project-robots --project . intelligence
./project-robots --project . impact
./project-robots --project . critique
./project-robots --project . autonomous --mode oneshot --issue "test"
```

## Linting

```bash
.venv/bin/ruff check .  # Clean (only # noqa: T201 for CLI prints)
```

## Safety

- Never commits/pushes
- Never installs deps
- Never edits product files
- Never deletes (clean-plan only lists)
- Checks from detected scripts or explicit profile
- Evidence bound to source fingerprint