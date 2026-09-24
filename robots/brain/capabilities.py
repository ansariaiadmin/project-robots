"""Capabilities — model tiers, static matrix, and dynamic probe handshake."""

from __future__ import annotations

import contextlib
import os
from dataclasses import dataclass, field
from pathlib import Path

TIER_1_LOCAL = "tier-1-local"
TIER_2_MID = "tier-2-mid"
TIER_3_FLAGSHIP = "tier-3-flagship"

TIER_BUDGETS = {
    TIER_1_LOCAL: 4000,
    TIER_2_MID: 16000,
    TIER_3_FLAGSHIP: 32000,
}

_TIER_3_HINTS = (
    "gpt-5", "gpt-4", "claude", "70b", "72b", "flagship", "opus", "o1", "o3",
    "gemini-ultra", "command-r-plus",
)
_TIER_2_HINTS = (
    "14b", "32b", "mixtral", "mistral-large", "qwen2.5:32b", "nemotron",
    "gemini-flash", "gpt-3.5",
)
_REASONING_HINTS = ("reason", "r1", "qwq", "think", "deepseek-r1", "o1", "qwen3")

TIER_ORDER = (TIER_1_LOCAL, TIER_2_MID, TIER_3_FLAGSHIP)

HANDSHAKE_PROMPT = 'Reply with exactly this JSON and nothing else: {"ok":true,"n":1}'
HANDSHAKE_TIMEOUT = 30
HANDSHAKE_TTL_SECONDS = 3600
HANDSHAKE_CACHE_NAME = "handshake-cache.json"


@dataclass(slots=True)
class CapabilityProfile:
    """Verified-or-classified capability snapshot for one model."""

    tier: str = TIER_1_LOCAL
    context_window: int = 4000
    tool_calling: bool = False
    reasoning_format: str = "none"  # "none" | "think-tags" | "native"
    structured_output: bool = False
    retrieval_budget: int = 4000
    retrieval_k: int = 8
    max_cycles: int = 2
    verification_depth: str = "shallow"  # "shallow" | "standard" | "deep"
    write_permission: str = "supervised"  # "denied" | "supervised" | "standard"
    model_known: bool = False
    provider: str = "mock"
    model: str = "mock-small"
    probes: dict = field(default_factory=dict)


def classify_model(model_name: str) -> CapabilityProfile:
    """Static tier classification from the model name (no network)."""
    name = (model_name or "").lower()
    if any(hint in name for hint in _TIER_3_HINTS):
        tier = TIER_3_FLAGSHIP
    elif any(hint in name for hint in _TIER_2_HINTS):
        tier = TIER_2_MID
    else:
        tier = TIER_1_LOCAL
    reasoning = "think-tags" if any(hint in name for hint in _REASONING_HINTS) else "none"
    profile = CapabilityProfile(
        tier=tier,
        context_window=TIER_BUDGETS[tier],
        reasoning_format=reasoning,
        model=model_name or "mock-small",
    )
    return _apply_tier_defaults(profile)


def _apply_tier_defaults(profile: CapabilityProfile) -> CapabilityProfile:
    if profile.tier == TIER_3_FLAGSHIP:
        profile.tool_calling = True
        profile.structured_output = True
        profile.retrieval_budget = 8000
        profile.retrieval_k = 15
        profile.max_cycles = 10
        profile.verification_depth = "deep"
        profile.write_permission = "standard"
    elif profile.tier == TIER_2_MID:
        profile.tool_calling = True
        profile.structured_output = True
        profile.retrieval_budget = 6000
        profile.retrieval_k = 12
        profile.max_cycles = 5
        profile.verification_depth = "standard"
        profile.write_permission = "standard"
    else:
        profile.tool_calling = False
        profile.structured_output = False
        profile.retrieval_budget = 4000
        profile.retrieval_k = 8
        profile.max_cycles = 2
        profile.verification_depth = "shallow"
        profile.write_permission = "supervised"
    return profile


def resolve_brain_config(config: dict, env: dict | None = None) -> dict:
    """Merge config["brain"] with autonomous pitfalls and env overrides (read-only)."""
    environ = env if env is not None else os.environ
    brain = config.get("brain", {}) if isinstance(config, dict) else {}
    if not isinstance(brain, dict):
        brain = {}
    merged = dict(brain)
    merged.setdefault("endpoint", environ.get("PROJECT_ROBOTS_MODEL_ENDPOINT", ""))
    merged.setdefault("model", environ.get("PROJECT_ROBOTS_MODEL_NAME", "mock-small"))
    merged.setdefault("provider", environ.get("PROJECT_ROBOTS_MODEL_PROVIDER", ""))
    merged.setdefault("timeout", 60)
    return merged


def probe_capabilities(
    provider, model: str, config: dict, verify: bool = False,
    project=None, force_probe: bool = False,
) -> CapabilityProfile:
    """Dynamic handshake: backend probe + live show + matrix + config overrides.

    Verification priority: explicit config > live probe > static matrix >
    conservative default. Never raises: every live step degrades gracefully
    with model_known=False and a recorded probe error.
    """
    profile = classify_model(model)
    profile.provider = getattr(provider, "kind", "mock")
    probes: dict = {"transport": "skipped"}
    try:
        info = provider.probe()
        probes = {
            "transport": "ok" if info.ok else "failed",
            "models_listed": len(info.models),
            "error": info.error,
        }
        if info.ok:
            profile.model_known = bool(info.model_known)
    except Exception as error:
        probes = {"transport": "failed", "error": str(error)}
        profile.model_known = False
    # Live model facts (Ollama /api/show + /api/tags): param count, context,
    # quantization, verified tool support. Beats name guessing.
    if getattr(provider, "kind", "") == "ollama" and probes["transport"] == "ok":
        try:
            facts = provider.model_facts(model)
            probes["facts"] = {k: v for k, v in facts.items() if k != "capabilities"}
            profile = apply_live_facts(profile, facts)
        except Exception as error:
            probes["facts_error"] = str(error)
    # OpenAI-compatible backends speak tool calling natively.
    if profile.provider == "openai":
        profile.tool_calling = True
        profile.structured_output = True
    # Explicit config override wins for context window.
    brain = config.get("brain", {}) if isinstance(config, dict) else {}
    override = brain.get("context_window") if isinstance(brain, dict) else None
    if override is not None:
        with contextlib.suppress(TypeError, ValueError):
            profile.context_window = int(override)
            probes["context_source"] = "config"
    # Micro-benchmark handshake: prove JSON validity + latency before tier commit.
    # A fresh per-(provider, endpoint, model) result is cached centrally for
    # HANDSHAKE_TTL_SECONDS so standard cycles skip the ~12s CPU penalty.
    if verify and profile.provider != "mock":
        handshake = None
        if project is not None and not force_probe:
            handshake = load_cached_handshake(
                project, profile.provider,
                getattr(provider, "endpoint", ""), model, config,
            )
        if handshake is None:
            handshake = verify_generation(provider, model)
            if handshake.get("json_valid"):
                save_cached_handshake(
                    project, profile.provider,
                    getattr(provider, "endpoint", ""), model, handshake,
                )
        else:
            handshake = {**handshake, "source": "cache"}
        probes["handshake"] = {k: v for k, v in handshake.items() if k != "text"}
        if not handshake["json_valid"]:
            profile.tier = step_down_tier(profile.tier)
            profile = _apply_tier_defaults(profile)
            probes["tier_stepdown"] = True
    elif profile.provider == "mock":
        probes["handshake"] = {"verified": True, "source": "mock"}
    profile.probes = probes
    return profile


def adaptive_params(profile: CapabilityProfile, configured: dict | None = None) -> dict:
    """Scale loop parameters by tier, never exceeding operator configuration."""
    configured = configured or {}
    try:
        configured_cycles = int(configured.get("max_cycles", profile.max_cycles))
    except (TypeError, ValueError):
        configured_cycles = profile.max_cycles
    try:
        configured_budget = int(configured.get("budget", profile.retrieval_budget))
    except (TypeError, ValueError):
        configured_budget = profile.retrieval_budget
    return {
        "tier": profile.tier,
        "max_cycles": max(1, min(configured_cycles, profile.max_cycles)),
        "verification_depth": profile.verification_depth,
        "budget": max(512, min(configured_budget, profile.retrieval_budget)),
        "retrieval_k": profile.retrieval_k,
        "write_permission": profile.write_permission,
        "context_window": profile.context_window,
    }


def resolve_runtime(
    config: dict, verify: bool = False, fast: bool = False,
    project=None, force_probe: bool = False,
) -> tuple:
    """Resolve (provider, profile, adaptive) for a config. Never raises.

    verify=True runs the generation handshake (slower, for real cycles);
    fast=True caps transport timeouts for cheap summary paths.
    project enables the handshake cache; force_probe bypasses it.
    """
    from robots.brain.provider import provider_from_config

    try:
        provider = provider_from_config(config)
    except Exception:
        provider = provider_from_config({})
    if fast:
        with contextlib.suppress(TypeError, ValueError):
            provider.timeout = min(int(getattr(provider, "timeout", 60)), 10)
    model = getattr(provider, "model", "") or "mock-small"
    try:
        auto_cfg = config.get("autonomous", {}) if isinstance(config, dict) else {}
        force = bool(auto_cfg.get("force_probe", False)) if isinstance(auto_cfg, dict) else False
        profile = probe_capabilities(
            provider, model, config, verify=verify, project=project, force_probe=force
        )
    except Exception:
        profile = classify_model(model)
    auto = config.get("autonomous", {}) if isinstance(config, dict) else {}
    limits = config.get("limits", {}) if isinstance(config, dict) else {}
    configured = {
        "max_cycles": (auto or {}).get("max_cycles", profile.max_cycles)
        if isinstance(auto, dict) else profile.max_cycles,
        "budget": (limits or {}).get("contextTokenBudget", profile.retrieval_budget)
        if isinstance(limits, dict) else profile.retrieval_budget,
    }
    return provider, profile, adaptive_params(profile, configured)


def parse_param_count(value: object) -> int | None:
    """Parse '7.6B' / 7615616512 style parameter counts to an int."""
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return int(value) if value > 0 else None
    if isinstance(value, str):
        text = value.strip().upper().replace(",", "")
        multipliers = {"B": 1_000_000_000, "M": 1_000_000, "K": 1_000}
        for suffix, factor in multipliers.items():
            if text.endswith(suffix):
                try:
                    return int(float(text[: -len(suffix)]) * factor)
                except ValueError:
                    return None
    return None


def parse_model_facts(tags_entry: dict, show: dict) -> dict:
    """Normalize /api/tags entry + /api/show payload into model facts (pure)."""
    tags_entry = tags_entry if isinstance(tags_entry, dict) else {}
    show = show if isinstance(show, dict) else {}
    details = show.get("details", {})
    if not isinstance(details, dict):
        details = {}
    tag_details = tags_entry.get("details", {})
    if not isinstance(tag_details, dict):
        tag_details = {}
    model_info = show.get("model_info", {})
    if not isinstance(model_info, dict):
        model_info = {}
    param_count = parse_param_count(model_info.get("general.parameter_count"))
    if param_count is None:
        param_count = parse_param_count(details.get("parameter_size"))
    if param_count is None:
        param_count = parse_param_count(tag_details.get("parameter_size"))
    context_length = tag_details.get("context_length")
    try:
        context_length = int(context_length) if context_length else None
    except (TypeError, ValueError):
        context_length = None
    capabilities = show.get("capabilities", [])
    if not isinstance(capabilities, list):
        capabilities = []
    quantization = details.get("quantization_level") or tag_details.get("quantization_level") or ""
    return {
        "param_count": param_count,
        "parameter_size": details.get("parameter_size") or tag_details.get("parameter_size") or "",
        "quantization": str(quantization),
        "context_length": context_length,
        "capabilities": [str(c) for c in capabilities],
    }


def tier_for_params(param_count: int | None) -> str | None:
    """Tier from verified parameter count (None when unknown)."""
    if param_count is None:
        return None
    if param_count <= 9_000_000_000:
        return TIER_1_LOCAL
    if param_count <= 35_000_000_000:
        return TIER_2_MID
    return TIER_3_FLAGSHIP


def step_down_tier(tier: str) -> str:
    """One conservative step down the tier ladder (floor at TIER_1)."""
    if tier in TIER_ORDER:
        return TIER_ORDER[max(0, TIER_ORDER.index(tier) - 1)]
    return TIER_1_LOCAL


def apply_live_facts(profile: CapabilityProfile, facts: dict) -> CapabilityProfile:
    """Override matrix classification with verified live facts (pure)."""
    facts = facts if isinstance(facts, dict) else {}
    live_tier = tier_for_params(facts.get("param_count"))
    if live_tier is not None:
        profile.tier = live_tier
        profile = _apply_tier_defaults(profile)
    capabilities = facts.get("capabilities", [])
    if isinstance(capabilities, list) and capabilities:
        lowered = [str(c).lower() for c in capabilities]
        profile.tool_calling = "tools" in lowered
    context_length = facts.get("context_length")
    if isinstance(context_length, int) and context_length > 0:
        profile.context_window = context_length
    return profile


def validate_handshake_text(text: str) -> tuple[bool, int]:
    """Validate the micro-benchmark handshake reply (pure)."""
    from robots.brain.prompt import extract_json

    data = extract_json(text or "")
    if not isinstance(data, dict):
        return False, -1
    if data.get("ok") is True:
        number = data.get("n", 1)
        return True, int(number) if isinstance(number, int) else -1
    return False, -1


def verify_generation(provider, model: str, timeout: int = HANDSHAKE_TIMEOUT) -> dict:
    """Micro-benchmark: prove JSON validity + latency. Never raises."""
    if getattr(provider, "kind", "") == "mock":
        return {"verified": True, "json_valid": True, "latency_ms": 0, "source": "mock", "text": ""}
    try:
        from robots.brain.provider import ModelOptions

        response = provider.generate(
            HANDSHAKE_PROMPT, ModelOptions(temperature=0.0, num_predict=32, timeout=timeout)
        )
    except Exception as error:
        return {"verified": False, "json_valid": False, "latency_ms": -1,
                "error": str(error), "text": ""}
    valid, _ = validate_handshake_text(response.text)
    return {
        "verified": valid and not bool(response.error),
        "json_valid": valid,
        "latency_ms": int(response.latency_ms),
        "error": response.error,
        "source": getattr(provider, "kind", "unknown"),
        "text": response.text[:200],
    }


def handshake_cache_path(project) -> Path | None:
    """Central cache file for handshake results (None without a project)."""
    if project is None:
        return None
    try:
        from robots.common import cache_dir

        return cache_dir(Path(project), "brain") / HANDSHAKE_CACHE_NAME
    except Exception:
        return None


def _handshake_ttl(config: dict) -> int:
    brain = config.get("brain", {}) if isinstance(config, dict) else {}
    if isinstance(brain, dict) and brain.get("handshake_ttl") is not None:
        with contextlib.suppress(TypeError, ValueError):
            return max(60, int(brain["handshake_ttl"]))
    return HANDSHAKE_TTL_SECONDS


def load_cached_handshake(
    project, provider_kind: str, endpoint: str, model: str, config: dict
) -> dict | None:
    """Return a fresh cached handshake for this backend+model, else None."""
    import json as _json
    import time as _time

    path = handshake_cache_path(project)
    if path is None or not path.is_file():
        return None
    try:
        cached = _json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(cached, dict):
        return None
    if cached.get("provider") != provider_kind or cached.get("model") != model:
        return None
    if cached.get("endpoint", "") != (endpoint or ""):
        return None
    try:
        age = _time.time() - float(cached.get("ts", 0))
    except (TypeError, ValueError):
        return None
    if age > _handshake_ttl(config):
        return None
    result = cached.get("result")
    if not isinstance(result, dict) or not result.get("json_valid"):
        return None
    return result


def save_cached_handshake(
    project, provider_kind: str, endpoint: str, model: str, result: dict
) -> bool:
    """Persist a valid handshake result centrally. Never raises."""
    import json as _json
    import time as _time

    path = handshake_cache_path(project)
    if path is None or not isinstance(result, dict):
        return False
    try:
        path.write_text(
            _json.dumps({
                "provider": provider_kind,
                "endpoint": endpoint or "",
                "model": model,
                "ts": _time.time(),
                "result": result,
            }) + "\n",
            encoding="utf-8",
        )
        return True
    except OSError:
        return False
