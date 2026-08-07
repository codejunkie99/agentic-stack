"""Tests for the shared LLM helper, focused on the MiniMax provider wiring."""
from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest import mock
from types import SimpleNamespace as _NS  # noqa: F401

ROOT = Path(__file__).resolve().parents[1]
HARNESS = ROOT / ".agent" / "harness"
sys.path.insert(0, str(HARNESS))

import llm  # noqa: E402  (path set up above)


class _Recorder:
    """Captures constructor kwargs for fake SDK clients."""

    def __init__(self):
        self.kwargs = None
        self.calls = []

    def factory(self):
        outer = self

        class FakeClient:
            def __init__(self, **kwargs):
                outer.kwargs = kwargs

            class messages:
                @staticmethod
                def create(**kwargs):
                    outer.calls.append(("anthropic", kwargs))
                    return _NS(content=[_NS(text="ok-anthropic")])

            class chat:
                class completions:
                    @staticmethod
                    def create(**kwargs):
                        outer.calls.append(("openai", kwargs))
                        return _NS(
                            choices=[_NS(message=_NS(content="ok-openai"))]
                        )

        return FakeClient


class MiniMaxProviderTest(unittest.TestCase):
    def setUp(self):
        # Start from a clean env per test.
        for key in (
            "AGENT_PROVIDER", "AGENT_MODEL", "AGENT_MINIMAX_REGION",
            "AGENT_MINIMAX_WIRE", "MINIMAX_API_KEY",
            "ANTHROPIC_API_KEY", "OPENAI_API_KEY",
        ):
            os.environ.pop(key, None)

    def test_regions_and_models_match_target_config(self):
        self.assertEqual(
            set(llm.MINIMAX_REGIONS), {"global_en", "cn_zh"}
        )
        self.assertEqual(
            llm.MINIMAX_REGIONS["global_en"]["openai_base_url"],
            "https://api.minimax.io/v1",
        )
        self.assertEqual(
            llm.MINIMAX_REGIONS["global_en"]["anthropic_base_url"],
            "https://api.minimax.io/anthropic",
        )
        self.assertEqual(
            llm.MINIMAX_REGIONS["cn_zh"]["openai_base_url"],
            "https://api.minimaxi.com/v1",
        )
        self.assertEqual(
            llm.MINIMAX_REGIONS["cn_zh"]["anthropic_base_url"],
            "https://api.minimaxi.com/anthropic",
        )
        self.assertEqual(set(llm.MINIMAX_MODELS), {"MiniMax-M3", "MiniMax-M2.7"})
        self.assertEqual(llm.MINIMAX_MODELS["MiniMax-M3"]["context_window"], 1000000)
        self.assertEqual(llm.MINIMAX_MODELS["MiniMax-M2.7"]["context_window"], 204800)
        self.assertEqual(llm.MINIMAX_DEFAULT_MODEL, "MiniMax-M3")

    def test_llm_available_requires_minimax_key(self):
        os.environ["AGENT_PROVIDER"] = "minimax"
        self.assertFalse(llm.llm_available())
        os.environ["MINIMAX_API_KEY"] = "stub-key"
        self.assertTrue(llm.llm_available())

    def test_call_model_openai_wire_global(self):
        os.environ["AGENT_PROVIDER"] = "minimax"
        os.environ["MINIMAX_API_KEY"] = "stub-key"
        os.environ["AGENT_MINIMAX_REGION"] = "global_en"
        os.environ["AGENT_MINIMAX_WIRE"] = "openai"
        rec = _Recorder()
        with mock.patch.dict(sys.modules, {"openai": _NS(OpenAI=rec.factory())}):
            out = llm.call_model("sys", "hi", model="MiniMax-M3")
        self.assertEqual(out, "ok-openai")
        self.assertEqual(rec.kwargs["base_url"], "https://api.minimax.io/v1")
        self.assertEqual(rec.kwargs["api_key"], "stub-key")
        wire, kwargs = rec.calls[0]
        self.assertEqual(wire, "openai")
        self.assertEqual(kwargs["model"], "MiniMax-M3")
        self.assertEqual(kwargs["max_completion_tokens"], 4096)

    def test_call_model_anthropic_wire_cn(self):
        os.environ["AGENT_PROVIDER"] = "minimax"
        os.environ["MINIMAX_API_KEY"] = "stub-key"
        os.environ["AGENT_MINIMAX_REGION"] = "cn_zh"
        os.environ["AGENT_MINIMAX_WIRE"] = "anthropic"
        rec = _Recorder()
        with mock.patch.dict(sys.modules, {"anthropic": _NS(Anthropic=rec.factory())}):
            out = llm.call_model("sys", "hi", model="MiniMax-M2.7")
        self.assertEqual(out, "ok-anthropic")
        self.assertEqual(rec.kwargs["base_url"], "https://api.minimaxi.com/anthropic")
        self.assertEqual(rec.kwargs["api_key"], "stub-key")
        wire, kwargs = rec.calls[0]
        self.assertEqual(wire, "anthropic")
        self.assertEqual(kwargs["model"], "MiniMax-M2.7")

    def test_default_model_is_m3(self):
        os.environ["AGENT_PROVIDER"] = "minimax"
        os.environ["MINIMAX_API_KEY"] = "stub-key"
        rec = _Recorder()
        with mock.patch.dict(sys.modules, {"openai": _NS(OpenAI=rec.factory())}):
            llm.call_model("sys", "hi")
        _, kwargs = rec.calls[0]
        self.assertEqual(kwargs["model"], "MiniMax-M3")

    def test_unknown_region_raises(self):
        os.environ["AGENT_PROVIDER"] = "minimax"
        os.environ["MINIMAX_API_KEY"] = "stub-key"
        os.environ["AGENT_MINIMAX_REGION"] = "mars"
        with self.assertRaises(ValueError):
            llm.call_model("sys", "hi", model="MiniMax-M3")

    def test_unknown_model_raises(self):
        os.environ["AGENT_PROVIDER"] = "minimax"
        os.environ["MINIMAX_API_KEY"] = "stub-key"
        with self.assertRaises(ValueError):
            llm.call_model("sys", "hi", model="nope")

    def test_unknown_wire_raises(self):
        os.environ["AGENT_PROVIDER"] = "minimax"
        os.environ["MINIMAX_API_KEY"] = "stub-key"
        os.environ["AGENT_MINIMAX_WIRE"] = "grpc"
        with self.assertRaises(ValueError):
            llm.call_model("sys", "hi", model="MiniMax-M3")


if __name__ == "__main__":
    unittest.main()
