"""Product boundaries: evidence review, persistence, private IPC and cancellation."""
import json
import base64
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path
from unittest.mock import patch

from harness_manager.loops.process import run_profile
from harness_manager.workspaces.box import BoxProvider, ProviderError
from harness_manager.workspaces.service import WorkspaceService
from harness_manager.workspaces.server import make_server


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.service = WorkspaceService(Path(self.tmp.name))
        self.ws = self.service.create_workspace({"name": "Release desk", "goal": "Prepare a reviewed release."})

    def tearDown(self):
        self.service.close()
        self.tmp.cleanup()

    def source(self, **kwargs):
        return self.service.add_source(dict(workspaceId=self.ws["id"], name="Runbook", text="Run the test suite before a release.", **kwargs))

    def test_review_is_required_and_survives_restart(self):
        source = self.source()
        with self.assertRaisesRegex(ValueError, "Review"):
            self.service.start_run({"workspaceId": self.ws["id"], "task": "Summarize."})
        self.assertNotIn("Run the test suite", self.service.handover(self.ws["id"]))
        self.service.review_source({"id": source["id"], "approved": True})
        restored = WorkspaceService(Path(self.tmp.name))
        self.assertIn("Run the test suite", restored.handover(self.ws["id"]))
        self.assertIn(source["digest"], restored.handover(self.ws["id"]))

    def test_revocation_removes_evidence_from_next_bundle(self):
        source = self.source()
        self.service.review_source({"id": source["id"], "approved": True})
        bundle = self.service.bundle(self.ws["id"])
        self.assertEqual(bundle["bundle"]["schema_version"], 1)
        content = "\n".join(base64.b64decode(f["content_b64"]).decode() for f in bundle["bundle"]["files"])
        self.assertIn("Run the test suite", content)
        self.service.review_source({"id": source["id"], "approved": False})
        revoked = self.service.bundle(self.ws["id"])
        content = "\n".join(base64.b64decode(f["content_b64"]).decode() for f in revoked["bundle"]["files"])
        self.assertNotIn("Run the test suite", content)

    def test_secret_and_path_boundaries(self):
        with self.assertRaisesRegex(ValueError, "credential"):
            self.service.add_source({"workspaceId": self.ws["id"], "name": "secret", "text": "sk-" + "a" * 32})
        with self.assertRaises(ValueError):
            self.service.store.workspace_path("../../escape")
        with self.assertRaises(ValueError):
            self.service.review_source({"id": self.source()["id"], "approved": "yes"})
        self.assertEqual(len(self.service.sources(self.ws["id"])), 1)

    def test_source_deduplication(self):
        self.assertEqual(self.source()["id"], self.source()["id"])
        self.assertEqual(len(self.service.sources(self.ws["id"])), 1)

    def test_restart_marks_local_work_interrupted(self):
        run = self.service.store.create("run", {"workspaceId": self.ws["id"], "status": "running", "provider": "local"})
        restored = WorkspaceService(Path(self.tmp.name))
        self.assertEqual(restored.store.get("run", run["id"])["status"], "interrupted")

    def test_cloud_is_repeat_safe_and_does_not_inherit_by_default(self):
        workspace = self.service.create_workspace({"name": "Cloud", "goal": "Review", "provider": "box"})
        provider = BoxProvider("test-credential")
        with patch.object(provider, "request", return_value={"ok": True}) as request:
            provider.create(workspace)
            first = request.call_args
            provider.create(workspace)
            self.assertEqual(first, request.call_args)
            self.assertTrue(first.args[2]["noEnv"])
            self.assertEqual(first.args[2]["ttlSeconds"], 3600)
            self.assertTrue(first.kwargs["key"])
        with self.assertRaises(ProviderError):
            BoxProvider("")

    def test_process_cancellation_stops_owned_process(self):
        event = threading.Event()
        timer = threading.Timer(0.15, event.set)
        timer.start()
        started = time.monotonic()
        result = run_profile({"command": [sys.executable, "-c", "import time; time.sleep(30)"], "timeout_seconds": 20},
                             {}, Path(self.tmp.name), 1000, event)
        timer.join()
        self.assertEqual(result.status, "cancelled")
        self.assertLess(time.monotonic() - started, 3)

    def test_ipc_rejects_unauthenticated_and_browser_requests(self):
        server = make_server(self.service, "t" * 48)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}/rpc"
        def post(headers):
            req = urllib.request.Request(url, data=b'{"method":"snapshot"}', headers=headers)
            return urllib.request.urlopen(req)
        try:
            with self.assertRaises(urllib.error.HTTPError) as failure:
                post({})
            self.assertEqual(failure.exception.code, 401)
            failure.exception.close()
            with self.assertRaises(urllib.error.HTTPError) as failure:
                post({"Authorization": "Bearer " + "t" * 48, "Origin": "https://example.com"})
            self.assertEqual(failure.exception.code, 403)
            failure.exception.close()
            with post({"Authorization": "Bearer " + "t" * 48}) as response:
                result = json.load(response)
            self.assertEqual(result["result"]["workspaces"][0]["id"], self.ws["id"])
        finally:
            server.shutdown()
            server.server_close()
            thread.join()


if __name__ == "__main__":
    unittest.main()
