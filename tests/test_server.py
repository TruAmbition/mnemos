import http.client
import json
import shutil
import tempfile
import threading
import unittest
from pathlib import Path

from mnemos import core
from mnemos.server import MnemosServer


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.data = Path(self.temp.name) / "data"
        core.initialize(self.data, "Owner")
        for child in core.vault_path(self.data).iterdir():
            if child.is_dir():
                shutil.rmtree(child)
            else:
                child.unlink()
        self.document = core.save_document(self.data, {"id": "approved", "title": "Approved note", "body": "Safe instructions", "status": "verified"})
        core.save_document(self.data, {"id": "draft", "title": "Unreviewed note", "body": "Unreviewed details"})
        self.server = MnemosServer(("127.0.0.1", 0), self.data)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop_server)
        self.port = self.server.server_address[1]

    def stop_server(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def request(self, method="GET", path="/api/bootstrap", payload=None, headers=None):
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=5)
        self.addCleanup(connection.close)
        request_headers = dict(headers or {})
        request_headers.setdefault('X-Mnemos-Workspace', self.server.workspace_id)
        body = None
        if payload is not None:
            body = json.dumps(payload)
            request_headers.setdefault("Content-Type", "application/json")
        connection.request(method, path, body, request_headers)
        response = connection.getresponse()
        data = response.read()
        try:
            content = json.loads(data)
        except json.JSONDecodeError:
            content = data
        return response.status, dict(response.getheaders()), content

    def token(self, role):
        return core.issue_token(self.data, role, role.title())

    def test_connection_dashboard_is_local_owner_only(self):
        from unittest.mock import patch
        from mnemos import connections
        with patch.object(connections, 'inventory', return_value={'connections': []}):
            self.assertEqual(self.request(path='/api/connections')[0], 200)
            self.assertEqual(self.request(path='/api/connections', headers={'Authorization': 'Bearer ' + self.token('reader')})[0], 403)
            self.assertEqual(self.request(path='/api/connections', headers={'Origin': 'https://elsewhere.invalid'})[0], 403)
            self.server.setup_enabled = False
            self.assertEqual(self.request(path='/api/connections')[0], 403)

    def test_project_management_is_local_owner_only_and_workspace_guarded(self):
        from unittest.mock import patch
        from mnemos import projects
        with patch.object(projects, 'list_projects', return_value={'projects': []}), patch.object(projects, 'refresh_project', return_value={'unchanged': True}) as refresh:
            self.assertEqual(self.request(path='/api/projects')[0], 200)
            self.assertEqual(self.request('POST', '/api/projects/refresh', {'id': 'project-fixture'})[0], 200)
            refresh.reset_mock()
            for endpoint in ['/api/projects', '/api/projects/refresh', '/api/projects/remove', '/api/projects/automatic']:
                self.assertEqual(self.request('POST', endpoint, {}, {'X-Mnemos-Workspace': 'stale'})[0], 409)
                self.assertEqual(self.request('POST', endpoint, {}, {'Origin': 'https://elsewhere.invalid'})[0], 403)
                for role in ['reader', 'author']:
                    self.assertEqual(self.request('POST', endpoint, {}, {'Authorization': 'Bearer ' + self.token(role)})[0], 403)
            refresh.assert_not_called()
            self.server.setup_enabled = False
            self.assertEqual(self.request(path='/api/projects')[0], 403)

    def test_stop_requires_owner_workspace_and_managed_launcher(self):
        from unittest.mock import patch
        self.assertEqual(self.request('POST', '/api/runtime/stop', {})[0], 409)
        self.server.launcher_managed = True
        self.assertEqual(self.request('POST', '/api/runtime/stop', {}, {'X-Mnemos-Workspace': 'stale'})[0], 409)
        self.assertEqual(self.request('POST', '/api/runtime/stop', {}, {'Origin': 'https://attacker.invalid'})[0], 403)
        self.assertEqual(self.request('POST', '/api/runtime/stop', {}, {'Authorization': 'Bearer ' + self.token('reader')})[0], 403)
        with patch.object(self.server, 'shutdown') as shutdown:
            self.assertEqual(self.request('POST', '/api/runtime/stop', {})[0], 200)
            for _ in range(20):
                if shutdown.called:
                    break
                threading.Event().wait(.01)
            shutdown.assert_called_once()

    def test_local_owner_is_constrained_by_host_and_origin(self):
        status, _, content = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(content["session"]["role"], "owner")
        self.assertEqual(len(content["documents"]), 2)
        self.assertNotIn("tokens", content["settings"])
        self.assertEqual(self.request(headers={"Host": "attacker.example"})[0], 403)
        self.assertEqual(self.request(headers={"Origin": "https://attacker.example"})[0], 403)

    def test_reader_cannot_access_drafts_or_write_or_export(self):
        headers = {"Authorization": "Bearer " + self.token("reader")}
        status, _, content = self.request(headers=headers)
        self.assertEqual(status, 200)
        self.assertEqual([item["id"] for item in content["documents"]], ["approved"])
        self.assertEqual(content["settings"], {})
        self.assertEqual(self.request(path="/api/documents/draft", headers=headers)[0], 404)
        for path in ["/api/documents", "/api/settings", "/api/backups"]:
            self.assertEqual(self.request("POST", path, {}, headers)[0], 403)
        self.assertEqual(self.request(path="/api/export", headers=headers)[0], 403)

    def test_author_can_draft_but_cannot_verify(self):
        headers = {"Authorization": "Bearer " + self.token("author")}
        payload = {"title": "Author contribution", "body": "A useful technique", "status": "draft"}
        status, _, content = self.request("POST", "/api/documents", payload, headers)
        self.assertEqual(status, 200)
        self.assertEqual(content["document"]["author"], "Author")
        self.assertEqual(self.request("POST", "/api/documents", dict(payload, status="verified"), headers)[0], 403)

    def test_mutations_require_json_and_same_origin(self):
        self.assertEqual(self.request("POST", "/api/documents", {"title": "No"}, {"Content-Type": "text/plain"})[0], 415)
        self.assertEqual(self.request("POST", "/api/documents", {"title": "No"}, {"Origin": "https://attacker.example"})[0], 403)
        self.assertEqual(self.request("POST", "/api/documents", {"title": "No"}, {"Sec-Fetch-Site": "cross-site"})[0], 403)

    def test_login_cookie_logout_and_invalid_token_never_fall_back_to_owner(self):
        token = self.token("reader")
        status, headers, _ = self.request("POST", "/api/login", {"token": token})
        self.assertEqual(status, 200)
        cookie = headers["Set-Cookie"]
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        session_cookie = cookie.split(";")[0]
        self.assertEqual(self.request(headers={"Cookie": session_cookie})[2]["session"]["role"], "reader")
        status, headers, _ = self.request("POST", "/api/logout", {}, {"Cookie": session_cookie})
        self.assertEqual(status, 200)
        logged_out = headers["Set-Cookie"].split(";")[0]
        self.assertEqual(self.request(headers={"Cookie": logged_out})[2]["session"]["role"], "anonymous")
        self.assertEqual(self.request(headers={"Authorization": "Bearer invalid"})[2]["session"]["role"], "anonymous")
        self.assertEqual(self.request(headers={"Cookie": session_cookie})[2]["session"]["role"], "anonymous")

    def test_network_bind_requires_explicit_allowed_host(self):
        with self.assertRaises(core.MnemosError):
            MnemosServer(("0.0.0.0", 0), self.data)

    def test_require_auth_disables_local_owner_for_reverse_proxy(self):
        self.server.local_owner = False
        status, _, content = self.request()
        self.assertEqual(status, 200)
        self.assertEqual(content["session"]["role"], "anonymous")
        self.assertEqual(content["documents"], [])
        self.assertEqual(self.request("POST", "/api/documents", {"title": "Denied"})[0], 401)

    def test_revision_conflict_and_traversal(self):
        payload = dict(self.document, body="New content")
        self.assertEqual(self.request("POST", "/api/documents", payload)[0], 200)
        self.assertEqual(self.request("POST", "/api/documents", payload)[0], 409)
        for path in ["/../mnemos/core.py", "/%2e%2e/mnemos/core.py", "/.git/config"]:
            self.assertIn(self.request(path=path)[0], {400, 404})


if __name__ == "__main__":
    unittest.main()
