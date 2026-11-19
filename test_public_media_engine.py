import unittest

from engine.public_media_engine import _extract_mp4_urls, _safe_http_url


class PublicMediaEngineTests(unittest.TestCase):
    def test_extracts_unique_https_mp4_links(self):
        html = '''
        <video><source src="https://cdn.example.org/a.mp4"></video>
        <a href="https://cdn.example.org/a.mp4">same</a>
        <a href="http://cdn.example.org/insecure.mp4">ignore</a>
        '''
        self.assertEqual(
            _extract_mp4_urls(html),
            ["https://cdn.example.org/a.mp4"],
        )

    def test_rejects_non_https_and_invalid_urls(self):
        self.assertFalse(_safe_http_url("http://example.org/video.mp4"))
        self.assertFalse(_safe_http_url("javascript:alert(1)"))
        self.assertTrue(_safe_http_url("https://upload.wikimedia.org/image.jpg"))

    def test_empty_html_returns_no_assets(self):
        self.assertEqual(_extract_mp4_urls(""), [])


if __name__ == "__main__":
    unittest.main()
