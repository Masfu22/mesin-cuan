import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch

from engine import ai_engine


class _OllamaHandler(BaseHTTPRequestHandler):
    received = []

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8"))
        self.__class__.received.append((self.path, payload))
        body = json.dumps({"response": "OLLAMA_TEST_OK"}).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


class ProviderFallbackTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _OllamaHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.old_url = ai_engine.OLLAMA_BASE_URL
        ai_engine.OLLAMA_BASE_URL = f"http://127.0.0.1:{cls.server.server_port}"

    @classmethod
    def tearDownClass(cls):
        ai_engine.OLLAMA_BASE_URL = cls.old_url
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def test_provider_waterfall_moves_to_next_provider(self):
        calls = []

        def fail():
            calls.append("NVIDIA")
            raise RuntimeError("simulated provider outage")

        def gemini():
            calls.append("Gemini")
            return "GEMINI_TEST_OK"

        def should_not_run():
            calls.append("Ollama")
            return "unexpected"

        result = ai_engine._run_ai_fallback(
            "unit test",
            [("NVIDIA", fail), ("Gemini", gemini), ("Ollama", should_not_run)],
        )
        self.assertEqual(result, "GEMINI_TEST_OK")
        self.assertEqual(calls, ["NVIDIA", "Gemini"])

    def test_provider_waterfall_uses_ollama_after_cloud_failures(self):
        def fail():
            raise RuntimeError("simulated outage")

        result = ai_engine._run_ai_fallback(
            "unit test",
            [("NVIDIA", fail), ("Gemini", fail), ("Ollama", lambda: ai_engine._ollama_text("test-model", "hello"))],
        )
        self.assertEqual(result, "OLLAMA_TEST_OK")

    def test_gemini_key_rotation_reads_multiple_slots(self):
        names = ["GEMINI_API_KEY", "GEMINI_API_KEY_2", "GEMINI_API_KEY_3", "GEMINI_API_KEYS"]
        previous = {name: __import__("os").environ.get(name) for name in names}
        try:
            __import__("os").environ["GEMINI_API_KEY"] = "key-one"
            __import__("os").environ["GEMINI_API_KEY_2"] = "key-two"
            __import__("os").environ["GEMINI_API_KEY_3"] = "key-one"
            __import__("os").environ["GEMINI_API_KEYS"] = "key-three,key-two"
            self.assertEqual(
                ai_engine._gemini_api_keys(),
                ["key-one", "key-two", "key-three"],
            )
        finally:
            for name, value in previous.items():
                if value is None:
                    __import__("os").environ.pop(name, None)
                else:
                    __import__("os").environ[name] = value

    def test_ollama_text_http_contract(self):
        _OllamaHandler.received.clear()
        result = ai_engine._ollama_text("test-model", "hello text")
        self.assertEqual(result, "OLLAMA_TEST_OK")
        route, payload = _OllamaHandler.received[-1]
        self.assertEqual(route, "/api/generate")
        self.assertEqual(payload["model"], "test-model")
        self.assertEqual(payload["prompt"], "hello text")
        self.assertFalse(payload["stream"])

    def test_ollama_vision_http_contract(self):
        _OllamaHandler.received.clear()
        result = ai_engine._ollama_vision("test-vision", "describe", ["ZmFrZS1pbWFnZQ=="])
        self.assertEqual(result, "OLLAMA_TEST_OK")
        route, payload = _OllamaHandler.received[-1]
        self.assertEqual(route, "/api/generate")
        self.assertEqual(payload["model"], "test-vision")
        self.assertEqual(payload["images"], ["ZmFrZS1pbWFnZQ=="])
        self.assertFalse(payload["stream"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
