"""Provider — stdlib HTTP clients for LLM backends plus deterministic mock."""

from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import dataclass, field


class BrainError(RuntimeError):
    """Transport- or protocol-level brain failure (caller falls back)."""


@dataclass(slots=True)
class ModelOptions:
    """Generation options (provider-agnostic subset)."""

    temperature: float = 0.2
    num_predict: int = 1024
    timeout: int = 60
    extra: dict = field(default_factory=dict)


@dataclass(slots=True)
class ModelResponse:
    """Normalized generation result across providers."""

    text: str
    model: str
    provider: str
    latency_ms: int = 0
    done: bool = True
    error: str = ""


@dataclass(slots=True)
class ProbeInfo:
    """Result of a backend capability handshake."""

    ok: bool
    provider: str
    models: list[str] = field(default_factory=list)
    model_known: bool = False
    error: str = ""


def _post_json(url: str, payload: dict, timeout: int, headers: dict | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json", **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as error:
        raise BrainError(f"POST {url} failed: {error}") from error


def _get_json(url: str, timeout: int, headers: dict | None = None) -> dict:
    request = urllib.request.Request(url, headers=dict(headers or {}))
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read().decode("utf-8")
    except Exception as error:
        raise BrainError(f"GET {url} failed: {error}") from error
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as error:
        raise BrainError(f"GET {url} returned non-JSON: {error}") from error
    return data if isinstance(data, dict) else {"data": data}


class BaseProvider:
    """Common provider surface."""

    kind = "base"

    def __init__(self, endpoint: str = "", model: str = "", timeout: int = 60) -> None:
        self.endpoint = (endpoint or "").rstrip("/")
        self.model = model or ""
        self.timeout = int(timeout)

    def generate(self, prompt: str, options: ModelOptions | None = None) -> ModelResponse:
        raise NotImplementedError

    def probe(self) -> ProbeInfo:
        raise NotImplementedError


class OllamaProvider(BaseProvider):
    """Ollama backend: /api/generate (+ /api/chat fallback), /api/tags probe."""

    kind = "ollama"

    def generate(self, prompt: str, options: ModelOptions | None = None) -> ModelResponse:
        opts = options or ModelOptions(timeout=self.timeout)
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": opts.temperature, "num_predict": opts.num_predict},
        }
        started = time.monotonic()
        try:
            data = _post_json(f"{self.endpoint}/api/generate", payload, opts.timeout)
        except BrainError as error:
            return ModelResponse(text="", model=self.model, provider=self.kind, error=str(error))
        text = str(data.get("response", ""))
        if not text and isinstance(data.get("message"), dict):
            text = str(data["message"].get("content", ""))
        if not text:
            # Fallback to chat endpoint for chat-tuned servers.
            chat = {
                "model": self.model,
                "messages": [{"role": "user", "content": prompt}],
                "stream": False,
                "options": {"temperature": opts.temperature, "num_predict": opts.num_predict},
            }
            try:
                data = _post_json(f"{self.endpoint}/api/chat", chat, opts.timeout)
            except BrainError as error:
                return ModelResponse(text="", model=self.model, provider=self.kind, error=str(error))
            message = data.get("message", {})
            text = str(message.get("content", "")) if isinstance(message, dict) else ""
        latency = int((time.monotonic() - started) * 1000)
        if not text:
            return ModelResponse(
                text="",
                model=self.model,
                provider=self.kind,
                latency_ms=latency,
                done=False,
                error="empty response",
            )
        return ModelResponse(text=text, model=self.model, provider=self.kind, latency_ms=latency)

    def probe(self) -> ProbeInfo:
        try:
            data = _get_json(f"{self.endpoint}/api/tags", self.timeout)
        except BrainError as error:
            return ProbeInfo(ok=False, provider=self.kind, error=str(error))
        models = []
        for entry in data.get("models", []) or []:
            name = entry.get("name", "") if isinstance(entry, dict) else ""
            if name:
                models.append(str(name))
        want = self.model.lower()
        known = any(want in name.lower() or name.lower() in want for name in models)
        return ProbeInfo(ok=True, provider=self.kind, models=models, model_known=known)

    def show_model(self, model: str = "") -> dict:
        """Fetch live model metadata via POST /api/show (raises BrainError)."""
        name = model or self.model
        if not name:
            raise BrainError("no model name for /api/show")
        data = _post_json(f"{self.endpoint}/api/show", {"model": name}, self.timeout)
        return data if isinstance(data, dict) else {}

    def model_facts(self, model: str = "") -> dict:
        """Combine /api/tags details with /api/show metadata (raises BrainError)."""
        from robots.brain.capabilities import parse_model_facts

        name = (model or self.model).lower()
        tags = _get_json(f"{self.endpoint}/api/tags", self.timeout)
        entry: dict = {}
        for item in tags.get("models", []) or []:
            item_name = str(item.get("name", "")) if isinstance(item, dict) else ""
            if item_name and (name in item_name.lower() or item_name.lower() in name):
                entry = item if isinstance(item, dict) else {}
                break
        return parse_model_facts(entry, self.show_model(model or self.model))


class OpenAICompatibleProvider(BaseProvider):
    """OpenAI / vLLM / LocalAI backend: /v1/chat/completions, /v1/models probe."""

    kind = "openai"

    def __init__(
        self,
        endpoint: str = "",
        model: str = "",
        timeout: int = 60,
        api_key: str = "",
    ) -> None:
        super().__init__(endpoint, model, timeout)
        self.api_key = api_key

    def _headers(self) -> dict:
        if self.api_key:
            return {"Authorization": f"Bearer {self.api_key}"}
        return {}

    def generate(self, prompt: str, options: ModelOptions | None = None) -> ModelResponse:
        opts = options or ModelOptions(timeout=self.timeout)
        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": opts.temperature,
            "max_tokens": opts.num_predict,
        }
        started = time.monotonic()
        try:
            data = _post_json(f"{self.endpoint}/v1/chat/completions", payload, opts.timeout, self._headers())
        except BrainError as error:
            return ModelResponse(text="", model=self.model, provider=self.kind, error=str(error))
        text = ""
        try:
            choices = data.get("choices", [])
            if choices and isinstance(choices[0], dict):
                message = choices[0].get("message", {})
                text = str(message.get("content", "")) if isinstance(message, dict) else ""
        except (AttributeError, IndexError, KeyError):
            text = ""
        latency = int((time.monotonic() - started) * 1000)
        if not text:
            return ModelResponse(
                text="",
                model=self.model,
                provider=self.kind,
                latency_ms=latency,
                done=False,
                error="empty choices",
            )
        return ModelResponse(text=text, model=self.model, provider=self.kind, latency_ms=latency)

    def probe(self) -> ProbeInfo:
        try:
            data = _get_json(f"{self.endpoint}/v1/models", self.timeout, self._headers())
        except BrainError as error:
            return ProbeInfo(ok=False, provider=self.kind, error=str(error))
        models = []
        entries = data.get("data", [])
        if isinstance(entries, list):
            for entry in entries:
                entry_id = entry.get("id", "") if isinstance(entry, dict) else ""
                if entry_id:
                    models.append(str(entry_id))
        want = self.model.lower()
        known = any(want in name.lower() or name.lower() in want for name in models)
        return ProbeInfo(ok=True, provider=self.kind, models=models, model_known=known)


class MockProvider(BaseProvider):
    """Deterministic offline fallback: returns a schema-valid plan envelope."""

    kind = "mock"

    def generate(self, prompt: str, options: ModelOptions | None = None) -> ModelResponse:
        _ = prompt
        _ = options
        plan = {
            "rationale": "Mock offline plan: inspect impact analysis and verify with checks.",
            "steps": [
                {"action": "analyze", "target": "impact"},
                {"action": "fix", "target": "root_cause"},
                {"action": "test", "target": "verification"},
            ],
            "changes": [],
            "risk_note": "mock provider performs no writes beyond guardrails",
        }
        return ModelResponse(
            text=json.dumps(plan),
            model=self.model or "mock-small",
            provider=self.kind,
            latency_ms=0,
        )

    def probe(self) -> ProbeInfo:
        return ProbeInfo(
            ok=True,
            provider=self.kind,
            models=[self.model or "mock-small"],
            model_known=True,
        )


def provider_from_config(config: dict, env: dict | None = None) -> BaseProvider:
    """Build a provider from config["brain"] with env overrides.

    Env: PROJECT_ROBOTS_MODEL_ENDPOINT, PROJECT_ROBOTS_MODEL_NAME,
    PROJECT_ROBOTS_MODEL_PROVIDER, PROJECT_ROBOTS_MODEL_API_KEY.
    Unconfigured -> MockProvider (offline deterministic).
    """
    environ = env if env is not None else os.environ
    brain = config.get("brain", {}) if isinstance(config, dict) else {}
    if not isinstance(brain, dict):
        brain = {}
    auto = config.get("autonomous", {}) if isinstance(config, dict) else {}
    if not isinstance(auto, dict):
        auto = {}
    endpoint = brain.get("endpoint") or auto.get("endpoint") or environ.get("PROJECT_ROBOTS_MODEL_ENDPOINT", "")
    model = brain.get("model") or auto.get("model") or environ.get("PROJECT_ROBOTS_MODEL_NAME", "") or "mock-small"
    kind = (brain.get("provider") or auto.get("provider") or environ.get("PROJECT_ROBOTS_MODEL_PROVIDER", "")).lower()
    timeout = int(brain.get("timeout", auto.get("timeout", 60)))
    api_key = brain.get("api_key", "") or environ.get("PROJECT_ROBOTS_MODEL_API_KEY", "")
    endpoint = str(endpoint).strip()
    if not endpoint:
        return MockProvider("", model, timeout)
    if not kind:
        kind = "openai" if "/v1" in endpoint else "ollama"
    if kind == "openai":
        return OpenAICompatibleProvider(endpoint, model, timeout, api_key=api_key)
    if kind == "mock":
        return MockProvider(endpoint, model, timeout)
    return OllamaProvider(endpoint, model, timeout)
