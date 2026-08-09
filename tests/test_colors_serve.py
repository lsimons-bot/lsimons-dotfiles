"""Tests for colors/serve.py's /save endpoint authentication (issue #12).

Exercises the actual HTTP server (bound to 127.0.0.1 on an ephemeral
port) rather than calling handler methods directly, so the tests cover
exactly what a browser would see: Origin/Content-Type validation, the
per-process save token, and that concurrent saves each use their own
temp file.
"""

import http.client
import importlib.util
import json
import shutil
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


serve = load_module("dotfiles_colors_serve", REPO_ROOT / "colors" / "serve.py")

VALID_HTML_A = "<!doctype html>\n<html><head></head><body>A</body></html>\n"
VALID_HTML_B = "<!doctype html>\n<html><head></head><body>B</body></html>\n"


class ColorsServeSaveEndpointTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmpdir, ignore_errors=True)
        here = Path(self.tmpdir)
        target_html = here / "lsd-colors.html"
        target_html.write_text(
            "<!doctype html>\n<html><head></head><body>seed</body></html>\n",
            encoding="utf-8",
        )

        # Redirect the module's file targets into our scratch directory so
        # tests never touch the real colors/lsd-colors.html.
        serve.HERE = here
        serve.TARGET_HTML = target_html
        serve.TARGET_MD = here / "lsd-colors.md"
        serve.TARGET_JSON = here / "lsd-colors.json"

        self.server = serve.http.server.ThreadingHTTPServer(
            ("127.0.0.1", 0), serve.Handler
        )
        self.port = self.server.server_port
        self.token = "test-token-" + "a" * 16
        serve.Handler.save_token = self.token
        serve.Handler.expected_origin = f"http://127.0.0.1:{self.port}"
        self.origin = serve.Handler.expected_origin

        self.thread = threading.Thread(target=self.server.serve_forever)
        self.thread.start()
        self.addCleanup(self._shutdown)

    def _shutdown(self):
        self.server.shutdown()
        self.thread.join(timeout=5)
        self.server.server_close()

    def _post(self, body: bytes, headers: dict) -> http.client.HTTPResponse:
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("POST", "/save", body=body, headers=headers)
            resp = conn.getresponse()
            resp.read()  # drain
            return resp
        finally:
            conn.close()

    def _valid_headers(self):
        return {
            "Origin": self.origin,
            "Content-Type": "application/json",
            "X-LSD-Save-Token": self.token,
        }

    def _saved_html(self) -> str:
        return serve.TARGET_HTML.read_text(encoding="utf-8")

    def test_missing_origin_rejected(self):
        headers = self._valid_headers()
        del headers["Origin"]
        body = json.dumps({"html": VALID_HTML_A}).encode()
        resp = self._post(body, headers)
        self.assertGreaterEqual(resp.status, 400)
        self.assertLess(resp.status, 500)
        self.assertNotEqual(self._saved_html(), VALID_HTML_A)

    def test_wrong_origin_rejected(self):
        headers = self._valid_headers()
        headers["Origin"] = "http://evil.example"
        body = json.dumps({"html": VALID_HTML_A}).encode()
        resp = self._post(body, headers)
        self.assertGreaterEqual(resp.status, 400)
        self.assertLess(resp.status, 500)
        self.assertNotEqual(self._saved_html(), VALID_HTML_A)

    def test_missing_content_type_rejected(self):
        headers = self._valid_headers()
        del headers["Content-Type"]
        body = json.dumps({"html": VALID_HTML_A}).encode()
        resp = self._post(body, headers)
        self.assertGreaterEqual(resp.status, 400)
        self.assertLess(resp.status, 500)
        self.assertNotEqual(self._saved_html(), VALID_HTML_A)

    def test_wrong_content_type_rejected(self):
        headers = self._valid_headers()
        headers["Content-Type"] = "text/plain"
        body = json.dumps({"html": VALID_HTML_A}).encode()
        resp = self._post(body, headers)
        self.assertGreaterEqual(resp.status, 400)
        self.assertLess(resp.status, 500)
        self.assertNotEqual(self._saved_html(), VALID_HTML_A)

    def test_missing_token_rejected(self):
        headers = self._valid_headers()
        del headers["X-LSD-Save-Token"]
        body = json.dumps({"html": VALID_HTML_A}).encode()
        resp = self._post(body, headers)
        self.assertGreaterEqual(resp.status, 400)
        self.assertLess(resp.status, 500)
        self.assertNotEqual(self._saved_html(), VALID_HTML_A)

    def test_wrong_token_rejected(self):
        headers = self._valid_headers()
        headers["X-LSD-Save-Token"] = "not-the-right-token"
        body = json.dumps({"html": VALID_HTML_A}).encode()
        resp = self._post(body, headers)
        self.assertGreaterEqual(resp.status, 400)
        self.assertLess(resp.status, 500)
        self.assertNotEqual(self._saved_html(), VALID_HTML_A)

    def test_valid_save_succeeds_and_regenerates_sidecars(self):
        body = json.dumps({"html": VALID_HTML_A}).encode()
        resp = self._post(body, self._valid_headers())
        self.assertEqual(resp.status, 200)
        self.assertEqual(self._saved_html(), VALID_HTML_A)
        self.assertTrue(serve.TARGET_MD.exists())
        self.assertTrue(serve.TARGET_JSON.exists())
        # No stray temp files left behind.
        leftovers = list(Path(self.tmpdir).glob("*.tmp"))
        self.assertEqual(leftovers, [])

    def test_get_serves_page_with_save_token_meta(self):
        conn = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        try:
            conn.request("GET", "/")
            resp = conn.getresponse()
            page = resp.read().decode("utf-8")
        finally:
            conn.close()
        self.assertEqual(resp.status, 200)
        self.assertIn(f'content="{self.token}"', page)
        self.assertIn('name="lsd-save-token"', page)

    def test_concurrent_saves_use_separate_temp_files_and_dont_corrupt(self):
        bodies = [
            json.dumps({"html": VALID_HTML_A}).encode(),
            json.dumps({"html": VALID_HTML_B}).encode(),
        ]

        def do_save(body):
            return self._post(body, self._valid_headers()).status

        with ThreadPoolExecutor(max_workers=2) as pool:
            statuses = list(pool.map(do_save, bodies))

        self.assertEqual(statuses, [200, 200])
        final = self._saved_html()
        # Whichever save "won" the final rename, the result must be
        # exactly one of the two complete documents -- never a
        # byte-level interleaving of both (which a shared temp-file name
        # could produce).
        self.assertIn(final, (VALID_HTML_A, VALID_HTML_B))
        leftovers = list(Path(self.tmpdir).glob("*.tmp"))
        self.assertEqual(leftovers, [])


if __name__ == "__main__":
    unittest.main()
