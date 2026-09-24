# PROJECT_ROBOTS — Level 5 Autonomous Software Engineer

Standard-library-only project automation with compact evidence. Now upgraded to **Level 5 Autonomous Software Engineer** with repository intelligence, speculative execution, reflexion loops, adaptive tooling, and continuous learning.

---

## Quick Start

```bash
cd /home/ai/Desktop/work/PROJECT_ROBOTS
./project-robots --project /path/to/target init           # Create central profile
./project-robots --project /path/to/target discover       # Detect stack & scripts
./project-robots --project /path/to/target context        # Token-budgeted context pack
./project-robots --project /path/to/target docs           # Validate docs & links
./project-robots --project /path/to/target hygiene        # Find conflicts & risks
./project-robots --project /path/to/target plan           # Minimal check plan
./project-robots --project /path/to/target check --run    # Execute checks
./project-robots --project /path/to/target evidence       # Verify fresh evidence
./project-robots --project /path/to/target report         # Combined report
```

### Level 5 Commands

```bash
./project-robots --project /path/to/target intelligence   # Architecture & dependency analysis
./project-robots --project /path/to/target impact         # Speculative impact & risk score
./project-robots --project /path/to/target critique       # Senior-engineer plan review
./project-robots --project /path/to/target autonomous     # Full autonomous cycles
```

---

## Architecture Overview

```
PROJECT_ROBOTS/
├── project_robots.py          # Main CLI (14 commands)
├── project-robots             # Shell wrapper
├── pyproject.toml             # Config + dev deps (pytest, ruff)
├── .gitignore                 # Excludes .cache, __pycache__, .venv
├── profiles/                  # Central per-project profiles
│   ├── example.json           # Template profile
│   ├── ledger.json            # Financial/hardware tracking
│   └── <project>-<hash>.json  # Generated profiles
├── robots/
│   ├── common.py              # Shared primitives (git, fs, cache, config)
│   ├── protocol.py            # Composable Robot protocol + registry
│   ├── discovery_robot.py     # Project shape detection
│   ├── context_robot.py       # Token-budgeted context packs
│   ├── docs_robot.py          # Doc validation (links, duplicates, headings)
│   ├── hygiene_robot.py       # Conflicts, secrets, generated files, TODOs
│   ├── cleanup_robot.py       # Non-destructive cleanup candidates
│   ├── checks_robot.py        # Check routing + execution
│   ├── evidence_robot.py      # Stale evidence rejection
│   ├── report_robot.py        # Combined project report
│   ├── agent_brain.py         # Telemetry + ledger + health
│   ├── ledger.py              # Financial ledger
│   ├── telemetry.py           # System metrics
│   │
│   ├── intelligence/          # Repository Intelligence (NEW)
│   │   ├── graph_builder.py       # Import/call/data-flow graphs
│   │   ├── architecture.py        # Layer detection & boundary mapping
│   │   ├── coupling.py            # Git history change coupling
│   │   ├── invariants.py          # Contract/schema/SLO registry
│   │   ├── debt_index.py          # Complexity, churn, age metrics
│   │   ├── core.py                # RepositoryIntelligence model
│   │   └── robot.py               # IntelligenceRobot
│   │
│   ├── impact/                # Speculative Impact Analysis (NEW)
│   │   ├── static_reachability.py # Transitive dependency reachability
│   │   ├── mutation_engine.py     # Mutation testing (mutmut/builtin)
│   │   ├── property_fuzzer.py     # Property-based testing (Hypothesis)
│   │   ├── contract_diff.py       # API/schema breaking change detection
│   │   ├── risk_scorer.py         # Multi-factor risk scoring
│   │   └── robot.py               # ImpactRobot
│   │
│   ├── reflexion/             # Self-Critique Loop (NEW)
│   │   ├── critic.py              # 10 senior-engineer heuristics
│   │   ├── refiner.py             # Plan refinement from critique
│   │   └── robot.py               # CritiqueRobot
│   │
│   ├── tooling/               # Adaptive Tool Selection (NEW)
│   │   ├── selector.py            # Finding → optimal tool mapping
│   │   ├── ast_rewrite.py         # libcst/ruff structural rewrites
│   │   ├── semantic_patch.py      # comby/coccinelle pattern patches
│   │   ├── model_checker.py       # TLA+/Alloy for concurrency
│   │   ├── contract_tester.py     # Schema/contract validation
│   │   └── robot.py               # (uses tools internally)
│   │
│   ├── evidence/              # Evidence-Bound Delivery (NEW)
│   │   ├── adr.py                 # Architectural Decision Records
│   │   ├── observability.py       # Metrics, traces, structured logs
│   │   ├── rollback.py            # Feature flags, canary, auto-rollback
│   │   ├── package.py             # Immutable signed EvidencePackage
│   │   └── robot.py               # (internal use)
│   │
│   └── autonomous/            # Continuous Loop (NEW)
│       ├── loop.py                # Sense→Plan→Critique→Act→Learn
│       ├── learning.py            # Coupling, risk, critic learning
│       └── robot.py               # AutonomousMainRobot
│
├── tests/
│   └── test_robots.py         # 8 passing tests
└── .cache/                    # Evidence + context + reports (gitignored)
```

---

## Core Principles

| Principle | Implementation |
|-----------|----------------|
| **Standard Library Only** | Zero runtime dependencies; optional tools (mutmut, libcst, comby, Hypothesis) gracefully degrade |
| **Central Profiles** | Profiles stored in `PROJECT_ROBOTS/profiles/`, never in target repos |
| **Evidence-Bound** | Every check binds to source fingerprint (git commit + worktree digest) |
| **Plan-Only by Default** | `check --run` required for execution; safe preview always available |
| **Token-Budgeted Context** | Context packs respect 4000 token default; on-demand file opening |
| **Immutable Evidence** | ADR, observability hooks, rollback strategy per change |

---

## Level 5 Capabilities

### 1. Repository Intelligence
Builds a causal model before any action:
- **Import Graph** — Module-level dependencies (AST-based)
- **Architectural Layers** — Domain, Application, Infrastructure, Presentation, Tests, Shared
- **Boundary Validation** — Detects layer violations (e.g., Domain → Infrastructure)
- **Change Coupling** — 90-day git co-change matrix with frequency & recency
- **Invariant Registry** — Contracts, schemas, SLOs from code + config + docs
- **Debt Index** — Cyclomatic complexity, churn, age, ownership per file

### 2. Speculative Execution & Impact Analysis
Mandatory pre-execution simulation:
- **Static Reachability** — Transitive dependents from changed files (BFS on reverse imports)
- **Mutation Testing** — mutmut integration; fallback builtin; mutation score
- **Property Fuzzing** — Hypothesis for pure functions; builtin deterministic checks
- **Contract Diff** — OpenAPI/Protobuf/Pydantic breaking change detection
- **Risk Score** = 0.35×reachability + 0.25×coupling + 0.20×mutation_survival + 0.15×contract_breakage + 0.05×performance

| Risk Threshold | Action |
|----------------|--------|
| < 0.15 | Auto-apply |
| 0.15–0.30 | Fast-track human review |
| 0.30–0.50 | Full human review |
| > 0.50 | Reject; require architectural review |

### 3. Reflexion Loop (Self-Critique)
Before execution, plan undergoes senior-engineer critique (max 3 iterations):
1. **Root Cause** — Fixes cause, not symptom?
2. **Abstraction Level** — No leaky abstractions, no premature abstraction
3. **Error Surface** — Narrowed, not widened; no silent failures
4. **Temporal Coupling** — No hidden state, implicit contracts
5. **Migration Path** — Every dependent has upgrade path or deprecation notice
6. **Observability** — Metrics, traces, logs for production validation
7. **Performance Budget** — No O(n²) in hot paths
8. **ADR Quality** — Context, decision, alternatives, consequences documented
9. **Style Consistency** — Follows project architectural style
10. **Security** — Input validation, no eval/exec/pickle/shell, secrets handled

### 4. Adaptive Tool Selection
Per finding, optimal tool selected:
| Finding Type | Tool |
|--------------|------|
| Cross-cutting patterns (logging, retry, auth) | Semantic patch (comby/coccinelle) |
| Structural refactoring (extract, rename, move) | AST rewrite (libcst/ruff) |
| Concurrency/state logic | Model checking (TLA+/Alloy) |
| API/contract changes | Contract testing + migration shim |
| Algorithm/logic correctness | Property-based testing (Hypothesis) |
| Performance optimization | Microbenchmarks + statistical analysis |

### 5. Evidence-Bound Delivery
Every change produces immutable `EvidencePackage`:
- **ADR** — Context, decision, alternatives, consequences
- **Impact Analysis** — Blast radius, risk score, coupling hotspots
- **Verification Plan** — Mutation targets, property tests, contract tests
- **Observability Hooks** — Prometheus metrics, OpenTelemetry traces, structured logs, alert rules
- **Rollback Strategy** — Feature flag / canary / blue-green with SLO breach triggers
- **Signed Package** — SHA256 fingerprint + signature (placeholder for crypto)

### 6. Continuous Learning
Post-execution updates:
- **Coupling Matrix** — Actual vs predicted impact → adjust predictions
- **Risk Weights** — Prediction error per factor → rebalance weights
- **Critic Patterns** — False positive/negative tracking → confidence scores
- **Tool Effectiveness** — Success rate + duration → tool selection bias

---

## Configuration

### Universal Profile (`profiles/universal.json`)
```json
{
  "version": 2,
  "intelligence": { "enabled": true, "graph_depth": 3, "coupling_window_days": 90 },
  "impact": {
    "enabled": true,
    "mutation_timeout_seconds": 120,
    "property_test_count": 500,
    "risk_thresholds": { "auto_apply": 0.15, "fast_track": 0.30, "full_review": 0.50 }
  },
  "reflexion": { "enabled": true, "critic_persona": "senior_staff_engineer", "max_iterations": 3 },
  "tooling": { "ast_rewrite": true, "semantic_patch": true, "model_checking": false, "contract_testing": true },
  "autonomous": { "enabled": false, "max_cycles": 10, "learning_enabled": true, "canary_percentage": 10 },
  "evidence": { "adr_required": true, "observability_hooks": true, "rollback_strategy": "feature_flag" }
}
```

### Project-Local Override (`.project-robots.json` in target repo)
```json
{
  "extends": "universal",
  "name": "my-project",
  "intelligence": { "graph_depth": 4, "custom_layers": ["domain", "application", "infrastructure"] },
  "tooling": { "model_checking": true, "tla_specs": "specs/" }
}
```

---

## Usage Examples

### One-Shot Autonomous Cycle
```bash
./project-robots --project /path/to/proj autonomous --mode oneshot --issue "refactor payment service"
```

### Continuous Autonomous Mode
```bash
./project-robots --project /path/to/proj autonomous --mode continuous --max-cycles 50 --interval 300 --issue "tech debt reduction" --issue "security hardening"
```

### Impact Analysis Before PR
```bash
./project-robots --project /path/to/proj impact
# Returns risk score, blast radius, mutation score, breaking changes
```

### Architecture Health Check
```bash
./project-robots --project /path/to/proj intelligence
# Returns layer violations, coupling hotspots, debt summary, invariants
```

### Plan Critique
```bash
./project-robots --project /path/to/proj critique
# Returns critique findings + refined plan if needed
```

---

## Output Format

All commands emit compact one-line summary + evidence paths:
```
PASS: {"trackedFiles": 66, "textLikeFiles": 64, "projectKinds": 1}
output: /home/ai/Desktop/work/PROJECT_ROBOTS/.cache/project_robots-<hash>/discover/latest.json
```

Detailed JSON/Markdown cached under `.cache/<slug>/<section>/latest.{json,md}`.

---

## Testing

```bash
cd /home/ai/Desktop/work/PROJECT_ROBOTS
.venv/bin/python -m pytest tests/test_robots.py -v
# 8 tests passing
```

Linting:
```bash
.venv/bin/ruff check .
# Clean (only intentional # noqa: T201 for CLI prints)
```

---

## Safety Guarantees

- **Never commits/pushes** — No git write operations
- **Never installs deps** — No package manager invocations
- **Never edits product files** — Read-only or plan-only by default
- **Never deletes** — `clean-plan` only lists candidates
- **Checks from detected scripts** — Or explicit profile; no invented commands
- **Evidence bound to source** — Stale evidence rejected on source change

---

## Handoff Notes for Next Session

### Current State
- All 14 commands operational
- All 8 tests passing
- Ruff linting clean
- Full pipeline verified end-to-end

### Key Files to Understand
1. `project_robots.py` — CLI entry, command dispatch
2. `robots/common.py` — Shared primitives (git, config, cache, source_state)
3. `robots/protocol.py` — Robot protocol + registry
4. `robots/intelligence/core.py` — RepositoryIntelligence model + build_repository_intelligence()
5. `robots/impact/risk_scorer.py` — RiskScore + thresholds
6. `robots/reflexion/critic.py` — 10 heuristic checks
7. `robots/autonomous/loop.py` — Sense→Plan→Critique→Act→Learn cycle
8. `robots/evidence/package.py` — EvidencePackage + ADR + Observability + Rollback

### Known Limitations
- Mutation testing requires `mutmut` install (gracefully degrades)
- Model checking requires `tlc` (TLA+) or `alloy` (gracefully degrades)
- Semantic patching requires `comby` (gracefully degrades to builtin string replace)
- Cryptographic signing is placeholder (SHA256 hash)
- Coupling analyzer requires git repo (works without but limited)
- Autonomous continuous mode runs single test cycle then exits (scheduler needs daemonization)

### Recommended Next Steps
1. Add `tlc` (TLA+) and `alloy` to dev environment for model checking
2. Add `comby` for semantic patching
3. Implement proper cryptographic signing for EvidencePackage
4. Daemonize autonomous scheduler with proper signal handling
5. Add webhook/notification integration for autonomous mode
6. Create VS Code extension for inline risk scores
7. Add support for monorepo multi-project profiles

---

## License

Internal tooling — not for external distribution.

---

*Generated by Level 5 Autonomous Software Engineer — PROJECT_ROBOTS v0.1.0*