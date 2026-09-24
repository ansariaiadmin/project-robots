# PROJECT_ROBOTS Handoff

## Handoff Metadata
- Generated at: 2026-09-05 (UTC+03:30, Asia/Tehran)
- Repository: /home/ai/Desktop/work/PROJECT_ROBOTS
- Current branch: master
- Baseline commit: 6674198 baseline
- Working tree state: dirty (13 tracked-modified + 18 untracked entries incl. HANDOFF.md, test_p1/test_drain files; Level-5 dirs remain uncommitted; no reset/clean performed)
- Python version: 3.12.3 (.venv/bin/python)
- Runtime dependency policy: stdlib-only, Python >= 3.10, no installs (pyproject.toml:1-6)
- Last verified by: implementation engineer, 2026-09-05 drain (pytest 152 passed; ruff clean on drain-touched files except 1 pre-existing T201; CLI continuous single-issue PASS)

## Mission
- Original objective: Audit the agentic system, then implement approved P0 milestone (3 fixes), verify completely, and hand off without starting new work.
- Milestones completed: P0 (critique handoff + EvidenceStore.load + single rag-query dispatch), P1 executors (all selector labels handled; property/benchmark explicitly unsupported), and bounded continuous drain (multi-cycle until empty/capped, queue persisted to .cache/<slug>/autonomous/queue.json, no daemon).
- Scope intentionally excluded from all: learning feedback loop, evidence signing/rollback honesty, registry unification, verification-depth enforcement, config precedence + execute() config-drop fixes, ruff style debt in untouched files, utcnow deprecations, daemon/watch mode, concurrency/file locking.

## Executive Summary
Three surgical fixes, no architecture change. Autonomous run_cycle (robots/autonomous/loop.py:266) now critiques the plan it just built via CritiqueRobot.critique_plan_direct (robots/reflexion/robot.py:19), instead of reading stale cache checks/latest.json; any critical-severity finding forces a deny-policy blocked execution (blocked_by_critique=True) with zero target writes. EvidenceStore.load (robots/evidence/package.py:105) now returns the package on hit and None on miss/corrupt/malformed, never raising for a missing decision_id (fixes unbound-variable NameError). project_robots.py now has exactly one rag-query parser (line 176) and one dispatch (line 432); behavior and flags (--task/--k/--budget) unchanged. 8 new regression tests (tests/test_p0_milestone.py); full suite 129 passed (was 121).

## Repository State
- Important uncommitted changes that existed before this task (FACT, git status): modified: README.md, project_robots.py, pyproject.toml, robots/agent_brain.py, robots/checks_robot.py, robots/cleanup_robot.py, robots/common.py, robots/context_robot.py, robots/docs_robot.py, robots/hygiene_robot.py, robots/ledger.py, robots/report_robot.py, robots/telemetry.py. Untracked pre-existing: QUICK_REFERENCE.md, fix_gen.py, fix_loop.py, fix_loop2.py, robots/autonomous/, robots/brain/, robots/evidence/, robots/impact/, robots/intelligence/, robots/protocol/, robots/rag/, robots/reflexion/, robots/sovereignty/, robots/tooling/, tests/test_autonomous_guard.py, tests/test_brain.py, tests/test_phase3.py, tests/test_phase35.py, tests/test_phase4.py, tests/test_rag.py. Interpretation: all Level-5 subsystems are uncommitted work on top of baseline 6674198; review as unreviewed.
- Files changed by this task:
  - robots/reflexion/robot.py (added critique_plan_direct :19-76; inspect kept file-backed :78+)
  - robots/autonomous/loop.py (direct handoff :339-355; critical block :360-375; verification critique attachment :382-393; _learn accepts passed/ok :1036-1041)
  - robots/evidence/package.py (rewrote load :105-141)
  - project_robots.py (deleted duplicate rag-query dispatch block; now single dispatch :432-440)
  - tests/test_p0_milestone.py (new, 8 tests)
- Files intentionally not changed: everything else, including all pre-existing modified/untracked files above; no baseline files reverted.
- Potentially suspicious or unfinished areas: fix_gen.py/fix_loop.py/fix_loop2.py at repo root (ad-hoc repair scripts, untested, unknown provenance); .cache/ and .pytest_cache/ generated state; QUICK_REFERENCE.md claims clean lint (contradicted by ruff 822 errors).
- P1 baseline audit (FACT, verified 2026-09-05 via git status/diff/ls-files vs 6674198; no delete/reset/clean performed):
  - A. Tracked modifications (13, diff-proven pre-existing Level-5-era edits): README.md, project_robots.py, pyproject.toml, robots/agent_brain.py, robots/checks_robot.py, robots/cleanup_robot.py, robots/common.py, robots/context_robot.py, robots/docs_robot.py, robots/hygiene_robot.py, robots/ledger.py, robots/report_robot.py, robots/telemetry.py.
  - B. Untracked: HANDOFF.md, QUICK_REFERENCE.md, fix_gen.py, fix_loop.py, fix_loop2.py, full dirs robots/autonomous|brain|evidence|impact|intelligence|protocol|rag|reflexion|sovereignty|tooling, tests/test_autonomous_guard.py, test_brain.py, test_p0_milestone.py, test_p1_executors.py, test_continuous_drain.py, test_phase3.py, test_phase35.py, test_phase4.py, test_rag.py.
  - C. Demonstrably changed by P0/P1/drain (subset with verifiable hunks/tests): project_robots.py duplicate-dispatch removal hunk; robots/reflexion/robot.py critique_plan_direct; robots/autonomous/loop.py critique handoff + critical block (P0) and executor branches (P1); robots/autonomous/robot.py bounded drain (drain); robots/evidence/package.py load rewrite; tests/test_p0_milestone.py; tests/test_p1_executors.py; tests/test_continuous_drain.py; HANDOFF.md.
  - D. Provenance unverified (labelled unverified, must not be attributed): everything else inside the untracked Level-5 dirs and the 13 tracked diffs beyond the hunks above — no per-author commit evidence exists (single baseline commit), so pre-existing vs concurrent authorship cannot be proven from repo state alone.
  - E. Must not touch: .git internals, .venv/, .cache/, .pytest_cache/, .ruff_cache/, profiles/, any target project outside this repo; no installs, no commits/pushes/resets.

## Architecture Snapshot
Actual runtime flow (FACT, verified in source):
CLI (project_robots.py:222 main, parser :143-219) -> direct robot import dispatch (no registry use) -> AutonomousMainRobot (robots/autonomous/robot.py:18 inspect fan-out default/oneshot/continuous; continuous is a bounded drain :131+ until queue empty or max_cycles, queue persisted to .cache/<slug>/autonomous/queue.json) -> AutonomousRobot.run_cycle (loop.py:266): centralize cleanup_stray_target_state (:280) -> _resolve_brain (:287, fail-open) -> throttle_check (:298) -> SENSE build_repository_intelligence (:310, core.py:146 with 1h cache) + RAG query_for_context (:320, fail-open) -> PLAN _generate_plan (:327; ImpactRobot.inspect + static fallback + Brain LLM build_prompt/repair_plan) + sanitize_changes (:335) -> CRITIQUE critique_plan_direct (:339-355; Critic 10 heuristics critic.py:37-108 + refine_plan refiner.py:211) -> ACT select_tools (:357, selector.py:25 decision tree) + _execute_plan (:375; all six selector labels handled after P1: ast_rewrite + semantic_patch write paths, model_checker read-only verification, contract_tester pure compute, property_tester/benchmark + unknown labels explicit unsupported) gated by evaluate_write_policy (guard.py:102) + allowlist + dry-run -> VERIFY _verify_with_repair (:378; syntax _syntax_check_files:103 + suite _run_target_suite:121 + ImpactRobot re-inspect + ≤2 repairs) -> EVIDENCE create_evidence_package (package.py:129; ADR + observability + rollback templates, SHA256 fingerprint+signature) -> LEARN _learn (:392; in-memory learning_data + LearningEngine file state) + _record_ledger (:395; sovereignty SQLite append-only).
State handoff model: file-based central cache .cache/<slug>/<section>/latest.json via common.cache_dir (:120-124); plan dict is the envelope (decision_id/issue/changes/tools/execution/verification/brain/context_chunks); critique artifacts also written to critique/latest.json + checks/latest_refined.json for inspectability only (never read back by autonomous path after this milestone).

## Agent and Worker Inventory
- DiscoveryRobot | robots/discovery_robot.py | stack/script/shape detection | entry project_robots.py:237 discover | in: Path, out: payload+path | status: working | tests: indirect only | limits: no dedicated test.
- ContextRobot | robots/context_robot.py:build | token-budgeted context pack | entry :241 context | in: task/budget, out: json+md | status: working | tests: test_robots.py (budget/routes/ownership/ignore) | limits: none known.
- DocsRobot | robots/docs_robot.py:inspect | links/duplicates | entry :247 | status: working | tests: broken-link test | limits: none.
- HygieneRobot | robots/hygiene_robot.py:inspect | conflicts/secrets/TODO | entry :251 | status: working | tests: none dedicated | limits: untested secrets paths.
- CleanupRobot | robots/cleanup_robot.py:inspect | list-only candidates | entry :255 clean-plan | status: working, never deletes | tests: none | limits: none.
- ChecksRobot | robots/checks_robot.py:build_plan/execute | minimal validation + execution | entry :259 plan/check --run | status: working | tests: plan determinism, stale-evidence | limits: none.
- EvidenceRobot (legacy) | robots/evidence_robot.py:inspect | check-evidence freshness | entry :283 | status: working | tests: stale test | limits: distinct from evidence/package.py store.
- ReportRobot | robots/report_robot.py:build | combined report | entry :287 | status: working | tests: none | limits: none.
- IntelligenceRobot | robots/intelligence/robot.py:12 inspect | repo intelligence (graph+arch+coupling+invariants+debt) | entry :295 | in: project+config, out: RobotResult + intelligence/latest.json | status: working; execute() drops config (:39-40) | tests: none direct | limits: 1h file cache (core.py:158-165) may serve stale graph.
- ImpactRobot | robots/impact/robot.py:17 inspect | reachability+coupling+mutation+contract+property -> RiskScorer | entry :302 | status: working; execute() drops config (:112-113) | tests: none direct (exercised via loop _verify) | limits: mutation/property/contract are heuristic stubs without external binaries.
- CritiqueRobot | robots/reflexion/robot.py:14 | heuristic critique + refine | entries: CLI inspect :78 (file-backed, preserved) + autonomous critique_plan_direct :19 (new, in-memory) | in: plan+intelligence+issue+config, out: (CritiqueResult, refined_plan, RobotResult) | status: FIXED this milestone | tests: new P0 (direct-vs-stale, standalone) | limits: heuristics are keyword-based, not semantic.
- AutonomousMainRobot | robots/autonomous/robot.py:18 | CLI mode fan-out; continuous = bounded drain (_run_continuous) | entry :316 autonomous | status: drain DONE (multi-cycle, persisted queue, capped, failure-continues) | tests: guard + drain matrix (9) | limits: no daemon/watch, no locking.
- AutonomousRobot | robots/autonomous/loop.py:196 | sense-plan-critique-act-learn orchestrator | entry: via MainRobot + solve :452 | status: P0 critique gate + P1 full executor fan-out | tests: guard + phase4 solve + P0 critical-block + P1 executor/gate matrix (14) | limits: single-cycle only.
- RAGRobot + commands | robots/rag/robot.py:178 + build_index_command :19 + query_command :46 + query_for_context :145 | SQLite FTS5 tri-hybrid (lexical+structural+hashed vectors, RRF fuse, budget allocate) | entries: rag-index :418, rag-query :432 | status: FIXED duplicate dispatch this milestone | tests: test_rag.py 14 + new P0 path-count | limits: heuristic embeddings; stale index short-circuits to empty.
- Brain providers | robots/brain/provider.py:75 Base + Ollama :92 + OpenAI :176 + Mock | capability tiers classify/probe/handshake capabilities.py:58/119 | entry: probe-brain :338 + internal _resolve_brain | status: working fail-open | tests: test_brain.py 20 + phase3 | limits: mock-small default offline.
- Tool executors | robots/tooling/semantic_patch.py:25, ast_rewrite.py:25, model_checker.py:30, contract_tester.py:30, selector.py:25 | pattern/AST/model/contract selection+execution | entry: internal _execute_plan only (loop.py:750-935) | status: all labels handled after P1 — ast_rewrite/semantic_patch write paths unchanged; model_checker + contract_tester wired read-only/pure-compute; property_tester/benchmark have NO modules (selector-only labels) and return explicit unsupported | tests: P1 matrix (14) + selector-skips | limits: need comby/spatch/libcst/TLC/schematics/pact for full power; missing backends report unsupported (never success); protobuf/pydantic contract paths refused as unimplemented placeholders.
- Evidence package/store | robots/evidence/package.py:17/87 + adr.py + observability.py + rollback.py | signed record + ADR + hooks + rollback template | entry: internal create_evidence_package | status: load FIXED this milestone; sign/canary/rollback still stubs | tests: new P0 roundtrip/missing/legacy/corrupt | limits: signature is SHA256 (not crypto), canary/rollback always True.
- Sovereignty ledger | robots/sovereignty/ledger.py:157 record_event + estimates | append-only SQLite, test-isolated | entry: status :556 + internal _record_ledger | status: working | tests: isolation + phase3/4 cost tests | limits: value model is fixed estimates.
- Telemetry | robots/telemetry.py:12 + brain/resources.py | disk/mem/gpu + throttle | entry: internal | status: working fail-open | tests: host overload tests | limits: Linux-leaning.

## Changes Implemented
1. Autonomous critique handoff.
   - Problem: run_cycle critiqued stale cache checks/latest.json instead of the current plan; writes proceeded regardless of critique.
   - Root cause: CritiqueRobot.inspect (reflexion/robot.py:19 old) only knew file-backed input; loop.py:340-354 called inspect + re-read latest_refined.json.
   - Implementation: new explicit contract critique_plan_direct(plan, intelligence, issue, project, config) (robot.py:19-76) critiques in-memory plan, refines in-memory, writes critique/latest.json + checks/latest_refined.json for inspectability only. loop.py:339-355 uses it; has_critical (any finding.severity==critical) forces critique_passed=False; loop.py:360-375 builds deny-policy blocked execution (blocked_by_critique=True, zero tool_results) instead of _execute_plan; verification gains verification[critique] attachment (loop.py:382-393); _learn accepts CritiqueResult.passed or RobotResult.ok (loop.py:1036-1041). CLI inspect (:78+) unchanged and still file-backed.
   - Files/lines: robots/reflexion/robot.py:19-78; robots/autonomous/loop.py:339-355, 360-375, 382-393, 1036-1041.
   - Compatibility: CLI critique output schema unchanged; autonomous RobotResult/CycleResult shapes unchanged (added execution.blocked_by_critique + verification.critique keys only). Autonomous outcomes may change (intended: critical plans now blocked).
   - Safety: strengthened — critical critique is now a hard write gate in addition to existing risk/allowlist/dry-run gates. No guard weakened.
2. EvidenceStore.load.
   - Problem: return dedented outside loop left data unbound on miss -> NameError; corrupt/malformed files raised.
   - Root cause: control-flow indentation error (package.py:105-122 old).
   - Implementation: return inside loop on valid hit; skip unreadable/corrupt/non-dict/incomplete entries; return None after loop (package.py:105-141). Central-first then legacy order preserved.
   - Files/lines: robots/evidence/package.py:105-141.
   - Compatibility: callers expecting None on miss now get it; callers relying on exception on miss (none found) would change — checked: no in-repo caller depends on raise.
   - Safety: improved — absence is explicit None, not a crash; no trust change (sign/verify untouched).
3. Duplicate rag-query dispatch.
   - Problem: two identical if args.command==rag-query blocks.
   - Root cause: copy-paste; single parser (project_robots.py:176) but double dispatch (:432 + :442 old).
   - Implementation: deleted second block; one canonical dispatch remains (:432-440). Parser/flags/output unchanged.
   - Files/lines: project_robots.py:432-440 (one block).
   - Compatibility: none — args (--task/--k/--budget), payload keys, exit codes identical.
   - Safety: none.
4. P1 executor wiring (this milestone).
   - Problem: _execute_plan invoked only ast_rewrite + semantic_patch; model_checker/contract_tester/property_tester/benchmark selector labels fell through with no tool_result (comment "Other tools would be invoked here").
   - Reconnaissance (FACT): genuinely implemented modules are ast_rewrite (RewriteResult success/files_changed/changes/errors/preview; rewrite(file_path, refactoring_type, params, dry_run)), semantic_patch (PatchResult same shape; apply_patch/apply_semantic_patch with dry_run + allowed_files), model_checker (ModelCheckResult success/properties_verified/violations/counterexamples/errors; check(spec_path, properties, spec_type) + run_model_check; builtin returns success=True/properties 0 with "No model checker available" error; Alloy path returns success=True with "not fully implemented"), contract_tester (ContractTestResult success/contracts_tested/passed/failed/breaking_changes/migration_shim/errors; test_contracts(old,new,type) with REAL openapi diff, protobuf/pydantic placeholders returning fake success=True). No property_tester or benchmark module exists anywhere (only selector.py:15,129,141-144 labels). Risk policy evaluated once at _execute_plan top via evaluate_write_policy; dry_run = policy.decision != allow; results persisted as execution.tool_results entries, serialized via _tool_dict into plan + evidence package.
   - Implementation: loop.py:796-935 new elif branches. model_checker: deny->blocked; missing spec_path->skipped; normalize_rel/is_in_scope fail->blocked; absent file->skipped; else ModelChecker(config).check(); backend-missing errors ("No model checker available"/"not fully implemented")->unsupported success False (never success); else status success/failed + dry_run flag. contract_tester: deny->blocked; non-dict specs->skipped; protobuf/pydantic->unsupported (refuse fake success); else ContractTester(config).test_contracts(); "requires model imports"->unsupported; else status success/failed. property_tester/benchmark: deny->blocked else unsupported (no module). Unknown labels: unsupported. All new results carry files_changed 0 so _written_files/ledger stay clean; read-only executors never write (no new shell, no new deps).
   - Files/lines: robots/autonomous/loop.py:796-935; tests/test_p1_executors.py (new, 14 tests).
   - Compatibility: existing tool_result entries unchanged; new status/dry_run keys additive; evidence/ledger shapes unchanged.
   - Safety: strengthened — deny blocks read-only executors too; out-of-scope reads blocked; missing context fails closed; unavailable backends can never report success.
5. Bounded continuous drain (this milestone).
   - Problem: continuous mode ran exactly one cycle per invocation ("Run one cycle to test"); max_cycles/interval accepted but ineffective; singular CLI issue key vs plural programmatic key; queue in-memory only.
   - Implementation: robot.py _run_continuous is now a bounded drain: _normalize_issues merges issues[] + issue (blanks dropped); empty fresh input resumes persisted queue.json remainder; missing/malformed queue data means empty; initial queue persisted before processing; one run_cycle per issue until empty or max_cycles (min(config, brain/adaptive cap, unchanged contract)); failure continues (run_cycle never raises); sleep interval_seconds only between executed cycles, never before first; queue re-persisted after each cycle; file removed on normal completion, preserved remainder on max_cycles stop. Result aggregates _run_default-style (cycles_completed/successful/failed/remaining + per-cycle metadata). No CLI flag changes, no daemon, no locking, run_cycle safety gates untouched.
   - Files/lines: robots/autonomous/robot.py (imports + helpers + _run_continuous, ~:1-260); tests/test_continuous_drain.py (new, 9 tests).
   - Compatibility: empty-queue message shape unchanged; multi-cycle summary is new (mode/cycles_completed/successful/failed/remaining/tier) replacing the old single-cycle continuous summary.
   - Safety: unchanged gates per cycle; zero new write paths (queue lives in central .cache, never the target tree).

## Tests and Verification
- Drain results (FACT, ran 2026-09-05): .venv/bin/python -m pytest -q -> 152 passed, 0 failures (143 + 9 new). tests/test_continuous_drain.py alone: 9 passed (3-drain clears queue+order, max-cap preserves remainder c, empty ok, singular issue, malformed queue as empty, resume persisted x/y, failure-continues 1/1, sleep exactly 2x between 3 cycles, no sleep single cycle). .venv/bin/ruff check robots/autonomous/robot.py tests/test_continuous_drain.py -> 1 error T201 print at robot.py:307 (__main__ block, pre-existing, untouched). ./project-robots --project . autonomous --mode=continuous --issue=drain-smoke --interval=0 -> PASS cycles_completed 1 remaining 0 EXIT 0.
- P1 results (preserved, FACT): pytest was 143 passed; tests/test_p1_executors.py alone 14 passed; ruff clean on loop.py + test_p1; CLI critique PASS + oneshot PASS (unquoted multi-word --issue fails argparse — shell-quoting artifact, = form works).
- P1 tests (tests/test_p1_executors.py, 14): contract openapi success; openapi breaking -> failed with breaking_changes; contract missing context -> skipped; protobuf placeholder -> unsupported; model missing spec -> skipped; out-of-scope spec -> blocked; absent file -> skipped; no-backend -> unsupported-or-genuine (never fake success, files_changed 0); property+benchmark -> unsupported; unknown tool -> unsupported; dry-run zero writes (byte comparison); high-risk deny blocks all (byte comparison); out-of-scope ast write blocked + no file created; critical critique still blocks all tools (blocked_by_critique, empty tool_results, bytes unchanged).
- P0 results (preserved): pytest was 129 passed; P0 file 8 passed and still passes inside the 152.
  - .venv/bin/python -m pytest -q -> 129 passed, 29 warnings in 6.44s (baseline before task: 121 passed; +8 new P0 tests, 0 failures).
  - .venv/bin/ruff check <5 touched files> -> 36 errors (all style/whitespace/print/import-order class; no new syntax errors). Critical-only (E9,F): 2 errors, both pre-existing (project_robots.py:183 F841 unused impact var; robots/reflexion/robot.py:10 F401 unused Critic import) — not introduced by this task, left untouched per minimal-change rule.
  - ./project-robots --project . rag-query --task test -> WORK REQUIRED stale-index payload (hits 0, reason: run rag-index first), output .cache/.../rag/query-latest.json, EXIT 0. FACT: stale behavior preserved.
  - ./project-robots --project . critique -> PASS passed:true severity 0.03 findings 1, output .cache/.../critique/latest.json, EXIT 0. FACT: standalone file-backed path works.
  - ./project-robots --project . autonomous --mode oneshot --issue test -> PASS cycle_id cycle-0000-d7c39183 success true evidence same id tier tier-1-local, output .cache/.../autonomous/latest.json, EXIT 0. FACT: autonomous cycle works offline with mock brain.
- New tests (tests/test_p0_milestone.py, 8): direct-vs-stale critique; critical-blocks-writes full run_cycle (asserts blocked_by_critique + target file byte-identical); standalone inspect; EvidenceStore missing->None; roundtrip; legacy fallback; corrupt->None; single parser+dispatch (parse_args compat + source counts ==1).
- No test mocks away the bug: direct test uses real intelligence + real Critic; block test runs real run_cycle (only _generate_plan stubbed for determinism since LLM path is mock-static); evidence tests use real store on temp git projects; rag test uses real parser + source assertion.
- Remaining test gaps: multi-critical-category matrix; blocked-cycle evidence/ledger assertions; RAG indexed (non-stale) query compat; concurrent-cycle isolation.

## Safety Model
- Write permissions: solve requires --allow-writes (else dry-run); autonomous allow_writes/dry_run via config + _wants_dry_run (supervised tiers preview by default); brain write_permission denied forces deny (loop.py:716-719). Unchanged.
- Dry-run behavior: guarded_write_text preview-only diffs (guard.py:179-200, 200-line cap); policy.decision != allow -> dry_run. Unchanged.
- Risk gates: evaluate_write_policy (guard.py:102-155): risk > 0.5 hard-deny; risk > threshold (default 0.3) dry-run; else allow (still allowlisted). NEW: critical critique forces deny regardless of risk score.
- Scope/allowlist: build_allowlist existing-files-only no-globs (guard.py:84-99); is_path_allowed boundary+canonical+allowlist (:158-167); sanitize_changes drops malformed/out-of-scope; is_in_scope blocks symlink escape. Unchanged.
- Evidence behavior: packages fingerprinted (SHA256 first 16) + SHA256-signed (non-crypto stub, documented); store central-only + legacy read fallback; load now None-safe. Trust level unchanged (still stub signatures — see next steps).
- Rollback limitations: RollbackStrategy is a template/runbook; canary_deploy/rollback() return True placeholders (package.py:76-84) — NOT real deployment safety. Unchanged by this milestone.
- What this milestone did not weaken: no guard threshold lowered, no allowlist widened, no dry-run default flipped, no target-tree writes added (all state stays under .cache/<slug>/).

## Known Weaknesses
- Critical: none introduced; previously-reported C1 (stale critique), C2 (load NameError), C3 (duplicate dispatch) are FIXED and removed from active list.
- High:
  - Executor wiring DONE (P1): all selector labels produce explicit tool_results; property_tester/benchmark remain unsupported by design (no modules exist). Residual: TLA/Alloy/schematics/pact backends absent in this env so model checks report unsupported; openapi contract diff is real.
  - Continuous drain DONE: bounded multi-cycle with persisted queue; no daemon/watch, no locking. Residual: concurrent CLI invocations could race on queue.json/latest.json (ledger appends are safe).
  - Learning records but never adapts (learning.py:_measure_actual_coupling returns {}; actual_risk never set; get_adjusted_weights/get_coupling_adjustment never called in scorer/selector hot path).
  - Config precedence + execute() config-drop: common.load_config breaks after first candidate; Intelligence/Impact/Critique execute() call inspect(project,{}) dropping operator config.
  - Evidence trust gap: sign is SHA256 (not HMAC/sigstore); canary/rollback always True; verify() mutates fingerprint as side effect.
- Medium:
  - External binaries silently absent (comby/spatch/libcst/TLC) -> builtin limited paths with only errors-list signal; no availability surfaced in plan summary.
  - Intelligence 1h cache without git-fingerprint invalidation (core.py:158-165).
  - Throttle/shallow verification silently marks success True with checks skipped (_verify_execution shallow branch).
  - Ruff 822-error style debt + utcnow deprecations (adr.py:24, package.py:28, learning.py:23/52, core.py:24).
  - Refiner writes TODO: into ADR fields (refiner.py:189) which ships as evidence.
- Low: telemetry Linux-leaning with fallbacks; risk weights uncalibrated (risk_scorer.py:43-49); solve CLI duplicates ledger/value math from loop._record_ledger.

## Prioritized Next Steps
1. Priority P1 | Close learning loop | Evidence: learning.py:194-198 {} stub; _learn actual_risk default; scorer/selector never read adjustments | Proposed: RiskScorer accepts LearningEngine.get_adjusted_weights; ToolSelector consults get_best_tool/coupling; set actual_risk from post-verify suite | Risk: medium (weight drift; clamp+renormalize already exists) | Tests: overestimate simulation => weight decreases, renormalized sum 1.0 | Depends: P0 verification.critique attachment (done, use it as signal).
2. Priority P1 | Evidence honesty | Evidence: package.py:58-84 sign/canary/rollback stubs | Proposed: HMAC sign with env key (fail-open verify with warning), canary/rollback return Skipped-with-reason dicts surfaced in summary, fix verify() side-effect | Risk: low | Tests: roundtrip, tamper=>False, canary=>skipped | Depends: P0 load fix (done).
3. Priority P2 | Registry unification | Evidence: protocol.py:66 registry; main() never uses get_robot; base robots never register; RAG registers inside suppress | Proposed: register all robots at import, dispatch via get_robot, add list_robots smoke test | Risk: low | Tests: registry contains all 10+ names; CLI dispatch via registry | Depends: none.
4. Priority P2 | Verification-depth enforcement | Evidence: shallow branch returns skipped yet cycle success True | Proposed: policy — shallow may pass only for low-risk + explicit flag; standard/deep required otherwise; surface depth in summary | Risk: low-medium (may flip some cycles to fail) | Tests: shallow+high-risk => success False or blocked | Depends: P0 block mechanism (done, reuse pattern).
5. Priority P2 | Config precedence + execute propagation | Evidence: common.py:148-159 break; 3 robots execute(project,{}) | Proposed: merge universal<central<local without break; pass through config in execute() | Risk: low | Tests: local-overrides-central; execute preserves thresholds | Depends: none.

## Decisions Needed From Owner
1. Should critical critique remain a hard write block, or become advisory (dry-run preview) for certain tiers/projects?
2. Should a killed-then-resumed continuous drain prefer fresh CLI input (current) or the persisted remainder when both exist?
3. Accept HMAC-with-env-key for evidence signing, or require sigstore/KMS before trusting evidence gates?
4. Is single-host SQLite ledger sufficient, or is a centralized multi-host ledger required?
5. Keep stdlib-only (no libcst/comby/Hypothesis installs) with limited builtins, or allow optional deps with graceful fallback?
6. Is bounded drain sufficient for continuous needs, or is daemon/watch mode with locking required later?
7. May shallow verification ever yield success True, or must standard/deep pass for success?
8. Keep 1h intelligence cache or invalidate on git fingerprint change?
9. Who owns central .cache profiles in multi-project use — per-user or shared?

## Continuation Protocol
1. Read this file first.
2. Inspect git status (expect dirty baseline + P0/P1/drain edits; never reset/clean).
3. Verify the last milestone: run .venv/bin/python -m pytest -q (expect 152 passed), ./project-robots --project . critique, ./project-robots --project . autonomous --mode=continuous --issue=smoke-test --interval=0 (use = form for multi-word issues).
4. Do not assume the report is correct without checking source (line refs above).
5. Choose one bounded next item from Prioritized Next Steps (do not bundle).
6. Implement, test, review (no unrelated files, no target writes, no new deps, no weakened guards), update this file (move completed item out of Next Steps, append to Repository State + Changes + Tests), and report.

## Suggested Next Prompt
Implement the next bounded P1 item in /home/ai/Desktop/work/PROJECT_ROBOTS: close the learning loop. Feed LearningEngine adjustments into RiskScorer/ToolSelector and set actual_risk from post-verify results. Keep stdlib-only. Add regression tests (overestimate simulation => weight decreases, renormalized sum 1.0). Run .venv/bin/python -m pytest -q, .venv/bin/ruff check on touched files, and CLI smoke (autonomous oneshot + critique). Update HANDOFF.md and report. Do not touch evidence signing, registry, config precedence, executors, or scheduler.

## Final Status
COMPLETE

Bounded continuous drain implemented, tested (152 passed: 143 + 9 new), ruff shows only the pre-existing T201 on drain-touched files, CLI continuous smoke PASS. No baseline file reverted, no deps added, no guard weakened, no CLI flags changed, no daemon/locking introduced. Fresh CLI input wins over persisted remainder on conflict (owner may reverse this).
