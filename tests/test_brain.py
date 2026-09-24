"""Tests for the model-agnostic Brain (providers, tiers, prompts). Stdlib only."""

from __future__ import annotations

import json
import unittest

from robots.brain import (
    TIER_1_LOCAL,
    TIER_2_MID,
    TIER_3_FLAGSHIP,
    MockProvider,
    OllamaProvider,
    OpenAICompatibleProvider,
    adaptive_params,
    build_prompt,
    classify_model,
    probe_capabilities,
    provider_from_config,
    repair_plan,
    resolve_runtime,
)
from robots.brain.provider import BrainError, ModelOptions, _get_json, _post_json


class ProviderSelectionTests(unittest.TestCase):
    def test_unconfigured_yields_mock(self):
        provider = provider_from_config({})
        self.assertIsInstance(provider, MockProvider)
        self.assertEqual(provider.kind, "mock")

    def test_v1_endpoint_yields_openai(self):
        provider = provider_from_config({"brain": {"endpoint": "http://x:8000/v1"}})
        self.assertIsInstance(provider, OpenAICompatibleProvider)

    def test_plain_endpoint_yields_ollama(self):
        provider = provider_from_config({"brain": {"endpoint": "http://x:11434"}})
        self.assertIsInstance(provider, OllamaProvider)

    def test_env_overrides(self):
        env = {
            "PROJECT_ROBOTS_MODEL_ENDPOINT": "http://y:11434",
            "PROJECT_ROBOTS_MODEL_NAME": "qwen2.5:7b",
        }
        provider = provider_from_config({}, env=env)
        self.assertIsInstance(provider, OllamaProvider)
        self.assertEqual(provider.model, "qwen2.5:7b")

    def test_mock_generate_is_schema_valid(self):
        response = MockProvider("", "mock-small").generate("do things")
        self.assertTrue(response.done)
        self.assertEqual(response.error, "")
        plan, repaired, _ = repair_plan(response.text, "do things")
        self.assertFalse(repaired)
        self.assertIn("rationale", plan)

    def test_mock_probe(self):
        info = MockProvider("", "mock-small").probe()
        self.assertTrue(info.ok)
        self.assertTrue(info.model_known)

    def test_transport_failures_do_not_raise(self):
        provider = OllamaProvider("http://127.0.0.1:1", "qwen2.5:7b", timeout=1)
        response = provider.generate("hi", ModelOptions(timeout=1))
        self.assertNotEqual(response.error, "")
        info = provider.probe()
        self.assertFalse(info.ok)
        openai = OpenAICompatibleProvider("http://127.0.0.1:1", "x", timeout=1)
        response = openai.generate("hi", ModelOptions(timeout=1))
        self.assertNotEqual(response.error, "")

    def test_http_helpers_raise_brain_error(self):
        with self.assertRaises(BrainError):
            _post_json("http://127.0.0.1:1/api/generate", {}, 1)
        with self.assertRaises(BrainError):
            _get_json("http://127.0.0.1:1/api/tags", 1)


class TierTests(unittest.TestCase):
    def test_tier_matrix(self):
        self.assertEqual(classify_model("qwen2.5:7b").tier, TIER_1_LOCAL)
        self.assertEqual(classify_model("qwen2.5:32b").tier, TIER_2_MID)
        self.assertEqual(classify_model("qwen2.5:14b").tier, TIER_2_MID)
        self.assertEqual(classify_model("gpt-5").tier, TIER_3_FLAGSHIP)
        self.assertEqual(classify_model("claude-opus-4").tier, TIER_3_FLAGSHIP)
        self.assertEqual(classify_model("some-unknown-model").tier, TIER_1_LOCAL)

    def test_tier_budgets(self):
        self.assertEqual(classify_model("qwen2.5:7b").context_window, 4000)
        self.assertEqual(classify_model("qwen2.5:32b").context_window, 16000)
        self.assertEqual(classify_model("gpt-5").context_window, 32000)

    def test_prob_capabilities_fail_open(self):
        provider = OllamaProvider("http://127.0.0.1:1", "qwen2.5:32b", timeout=1)
        profile = probe_capabilities(provider, "qwen2.5:32b", {})
        self.assertEqual(profile.tier, TIER_2_MID)
        self.assertFalse(profile.model_known)
        self.assertEqual(profile.probes["transport"], "failed")

    def test_openai_kind_enables_tool_calling(self):
        provider = OpenAICompatibleProvider("http://x:8000/v1", "tiny", timeout=1)
        profile = probe_capabilities(provider, "tiny", {})
        self.assertTrue(profile.tool_calling)
        self.assertTrue(profile.structured_output)

    def test_adaptive_params_cap(self):
        profile = classify_model("qwen2.5:7b")
        adapted = adaptive_params(profile, {"max_cycles": 10, "budget": 99999})
        self.assertEqual(adapted["max_cycles"], 2)
        self.assertEqual(adapted["budget"], 4000)
        self.assertEqual(adapted["verification_depth"], "shallow")
        self.assertEqual(adapted["retrieval_k"], 8)

    def test_resolve_runtime_offline(self):
        _, profile, adapted = resolve_runtime({})
        self.assertEqual(profile.tier, TIER_1_LOCAL)
        self.assertEqual(adapted["max_cycles"], 2)


class PromptTests(unittest.TestCase):
    def test_tier1_xml_contract(self):
        prompt = build_prompt(task="fix leak", rag_chunks=[], tier=TIER_1_LOCAL)
        self.assertIn("<context", prompt)
        self.assertIn("<task>fix leak</task>", prompt)
        self.assertIn("<contract>", prompt)
        self.assertIn("JSON ONLY", prompt)

    def test_tier3_markdown_trace(self):
        chunks = [{"path": "a.py", "start": 1, "end": 5, "symbol": "f",
                   "rrf": 0.03, "text": "def f(): pass"}]
        prompt = build_prompt(task="fix leak", rag_chunks=chunks, tier=TIER_3_FLAGSHIP)
        self.assertIn("# Autonomous Repair Plan", prompt)
        self.assertIn("## Relevant Code", prompt)
        self.assertIn("a.py", prompt)

    def test_repair_valid(self):
        raw = json.dumps({"rationale": "r", "steps": [{"action": "a", "target": "t"}]})
        plan, repaired, error = repair_plan(raw, "task")
        self.assertFalse(repaired)
        self.assertEqual(error, "")
        self.assertEqual(plan["rationale"], "r")

    def test_repair_fenced(self):
        raw = "reasoning...\n```json\n{\"rationale\": \"r\", \"steps\": []}\n```"
        plan, repaired, _ = repair_plan(raw, "task")
        self.assertEqual(plan["rationale"], "r")
        self.assertTrue(repaired)  # empty steps filled with defaults
        self.assertGreater(len(plan["steps"]), 0)

    def test_repair_garbage(self):
        plan, repaired, error = repair_plan("not json at all", "my task")
        self.assertTrue(repaired)
        self.assertNotEqual(error, "")
        self.assertIn("my task", plan["rationale"])
        self.assertGreater(len(plan["steps"]), 0)

    def test_repair_cleans_steps(self):
        raw = json.dumps({
            "rationale": "r",
            "steps": [{"action": "a"}, "nope", {"action": "b", "target": "c"}],
        })
        plan, repaired, _ = repair_plan(raw, "task")
        self.assertTrue(repaired)
        self.assertEqual(plan["steps"], [{"action": "b", "target": "c"}])


if __name__ == "__main__":
    unittest.main()
