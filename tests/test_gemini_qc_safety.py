import json
import os
import tempfile
import unittest
from unittest.mock import patch

from types import SimpleNamespace
from unittest.mock import MagicMock

from engine import qc_vision_engine, script_engine, topic_engine
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


    def test_script_gemini_rotates_after_client_initialization_failure(self):
        calls = []
        response_text = json.dumps({
            "title": "Uji Rotasi Gemini",
            "script": "Ini adalah naskah pengujian rotasi kunci Gemini.",
            "keywords": ["uji", "gemini"],
            "tags": ["uji"],
            "description": "Pengujian rotasi API key.",
        })

        def client_factory(api_key, **_kwargs):
            calls.append(api_key)
            if api_key == "first-key":
                raise RuntimeError("simulated invalid key")
            models = SimpleNamespace(
                generate_content=lambda **_args: SimpleNamespace(text=response_text)
            )
            return SimpleNamespace(models=models)

        with patch.dict(os.environ, {
            "GEMINI_API_KEY": "first-key",
            "GEMINI_API_KEY_2": "second-key",
            "GEMINI_MODEL": "gemini-3.5-flash-lite",
        }, clear=False), patch("google.genai.Client", side_effect=client_factory):
            result = script_engine._call_gemini("system", "user", "shorts")

        self.assertEqual(calls, ["first-key", "second-key"])
        self.assertEqual(result["title"], "Uji Rotasi Gemini")

    def test_topic_gemini_rotates_keys_before_fallback_providers(self):
        calls = []

        def client_factory(api_key, **_kwargs):
            calls.append(api_key)
            if api_key == "first-key":
                raise RuntimeError("simulated invalid key")
            models = SimpleNamespace(
                generate_content=lambda **_args: SimpleNamespace(
                    text=json.dumps({"topics": ["Misteri yang belum terpecahkan hingga kini"]})
                )
            )
            return SimpleNamespace(models=models)

        with patch.dict(os.environ, {
            "NVIDIA_API_KEY": "",
            "GEMINI_API_KEY": "first-key",
            "GEMINI_API_KEY_2": "second-key",
            "GEMINI_MODEL": "gemini-3.5-flash-lite",
        }, clear=False), patch("google.genai.Client", side_effect=client_factory):
            topics = topic_engine._generate_candidates_via_ai("horror_facts", "id")

        self.assertEqual(calls, ["first-key", "second-key"])
        self.assertEqual(topics, ["Misteri yang belum terpecahkan hingga kini"])

    def test_qc_gemini_rotates_keys_when_first_key_cannot_upload(self):
        calls = []
        approved_json = json.dumps({
            "status": "APPROVED",
            "score": 9,
            "summary": "Video memenuhi kriteria QC.",
            "issues": [],
            "auto_fixable": [],
            "approved_aspects": ["audio", "visual"],
        })

        def client_factory(api_key, **_kwargs):
            calls.append(api_key)
            files = MagicMock()
            if api_key == "first-key":
                files.upload.side_effect = RuntimeError("simulated upload authorization failure")
                return SimpleNamespace(files=files, models=SimpleNamespace())
            files.upload.return_value = SimpleNamespace(
                name="files/qc-test",
                state=SimpleNamespace(name="ACTIVE"),
            )
            models = SimpleNamespace(
                generate_content=lambda **_args: SimpleNamespace(text=approved_json)
            )
            return SimpleNamespace(files=files, models=models)

        with tempfile.NamedTemporaryFile(suffix=".mp4") as video, patch.dict(os.environ, {
            "GEMINI_API_KEY": "first-key",
            "GEMINI_API_KEY_2": "second-key",
            "GEMINI_MODEL": "gemini-3.5-flash-lite",
        }, clear=False), patch("google.genai.Client", side_effect=client_factory):
            result = qc_vision_engine.review_video(
                video.name, "", {"title": "Test QC"}, {"id": "test-channel"}, "shorts"
            )

        self.assertEqual(calls, ["first-key", "second-key"])
        self.assertEqual(result["status"], "APPROVED")


if __name__ == "__main__":
    unittest.main(verbosity=2)
