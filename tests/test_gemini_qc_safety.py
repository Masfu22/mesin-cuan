import json
import os
import tempfile
import unittest
from unittest.mock import patch

from engine import qc_vision_engine, script_engine
from engine.utils import get_gemini_api_keys


class GeminiAndQCSafetyTests(unittest.TestCase):
    def test_shared_key_collector_reads_all_slots_and_deduplicates(self):
        values = {
            "GEMINI_API_KEY": "key-1",
            **{f"GEMINI_API_KEY_{i}": f"key-{i}" for i in range(2, 11)},
            "GEMINI_API_KEYS": "key-10,key-extra,key-1",
        }
        with patch.dict(os.environ, values, clear=False):
            keys = get_gemini_api_keys()
        self.assertEqual(len(keys), 11)
        self.assertEqual(keys[0], "key-1")
        self.assertEqual(keys[-1], "key-extra")

    def test_script_provider_waterfall_order(self):
        calls = []
        def fail(name):
            def _call(*_args, **_kwargs):
                calls.append(name)
                raise RuntimeError(name + " simulated failure")
            return _call
        def succeed(name):
            def _call(*_args, **_kwargs):
                calls.append(name)
                return {"title": "waterfall test", "script": "test"}
            return _call

        env = {
            "NVIDIA_API_KEY": "nvidia-test",
            "GEMINI_API_KEY": "gemini-test",
            "GROQ_API_KEY": "groq-test",
            "ANTHROPIC_API_KEY": "anthropic-test",
        }
        with patch.dict(os.environ, env, clear=False), \
             patch.object(script_engine, "_call_nvidia", fail("NVIDIA")), \
             patch.object(script_engine, "_call_gemini", fail("Gemini")), \
             patch.object(script_engine, "_call_groq", fail("Groq")), \
             patch.object(script_engine, "_call_anthropic", succeed("Anthropic")), \
             patch.object(script_engine, "get_provider_config", return_value={"api_key": "", "base_url": ""}), \
             patch.object(script_engine.time, "sleep"):
            result = script_engine._call_ai("system", "user", "shorts")
        self.assertEqual(calls, ["NVIDIA", "Gemini", "Groq", "Anthropic"])
        self.assertEqual(result["title"], "waterfall test")

    def test_qc_invalid_or_missing_decision_never_approves(self):
        malformed = qc_vision_engine._parse_qc_response("not json", "test-model")
        missing_status = qc_vision_engine._parse_qc_response(
            json.dumps({"score": 10, "issues": []}), "test-model"
        )
        self.assertEqual(malformed["status"], "QC_ERROR")
        self.assertEqual(missing_status["status"], "QC_ERROR")

    def test_qc_error_when_no_gemini_keys(self):
        with tempfile.NamedTemporaryFile(suffix=".mp4") as video, \
             patch.dict(os.environ, {}, clear=True):
            result = qc_vision_engine.review_video(
                video.name, "", {}, {"id": "test-channel"}, "shorts"
            )
        self.assertEqual(result["status"], "QC_ERROR")
        self.assertEqual(result["score"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
