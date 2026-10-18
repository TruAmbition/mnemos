"""Small same-origin web server. Deploy behind TLS for access beyond localhost."""
from __future__ import annotations

import ipaddress
import json
import mimetypes
import secrets
import threading
import time
import uuid
from contextlib import nullcontext
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from . import __version__, core, onboarding


def is_loopback(host: str) -> bool:
    if host.lower() == "localhost":
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


class MnemosServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, data_path, public_hosts=(), handler=None, require_auth=False, installation_file=None):
        supplied_data = Path(data_path).expanduser().absolute()
        if supplied_data.is_symlink():
            raise core.MnemosError('The Mnemos data folder must not be a symbolic link.')
        self.data_path = supplied_data.resolve()
        bound_loopback = is_loopback(address[0])
        self.local_owner = bound_loopback and not require_auth
        self.setup_enabled = self.local_owner and not public_hosts
        self.installation_file = Path(installation_file) if installation_file else None
        self.setup_lock = threading.Lock()
        self.workspace_lock = threading.RLock()
        self.workspace_id = uuid.uuid4().hex
        self.selection_fingerprint = None
        if self.installation_file:
            before = onboarding.selection_fingerprint(self.installation_file)
            selected = onboarding.load_selection(self.installation_file, self.installation_file.parent)
            self.workspace_id = onboarding.selection_revision(self.installation_file)
            self.selection_fingerprint = onboarding.selection_fingerprint(self.installation_file)
            if selected != self.data_path or before != self.selection_fingerprint:
                raise core.MnemosError('The default workspace changed while launching. Start the launcher again.')
        if (self.data_path / 'config.json').exists():
            core.load_config(self.data_path)
        elif not self.setup_enabled:
            raise core.MnemosError('Initialize the installation locally before enabling network or authenticated access.')
        if not bound_loopback and not public_hosts:
            raise core.MnemosError("Network sharing requires --public-host with the hostname readers will use.")
        self.sessions, self.login_failures = {}, {}
        self.connection_checks = {}
        self.launcher_managed = False
        self.stopping = False
        from .project_monitor import ProjectMonitor
        self.project_monitor = ProjectMonitor(self)
        from .git_backup import GitBackupMonitor
        self.git_backup_monitor = GitBackupMonitor(self)
        self.session_lock = threading.RLock()
        super().__init__(address, handler or Handler)
        port = self.server_address[1]
        from . import local_access
        self.local_key = local_access.create(self.installation_file.parent if self.installation_file else self.data_path, port) if self.local_owner else ''
        self.local_cookie = f'mnemos_local_{port}'
        local_names = ["localhost", "127.0.0.1", "[::1]"] if bound_loopback else []
        self.allowed_hosts = {f"{name}:{port}" for name in local_names}
        if port == 80:
            self.allowed_hosts.update(local_names)
        for name in public_hosts:
            if "/" in name or "@" in name or "\n" in name or "\r" in name:
                self.server_close()
                raise core.MnemosError("--public-host must be a hostname, optionally including its port.")
            self.allowed_hosts.add(name.lower())

    def active_workspace(self, include_path=True):
        result = {'revision': self.workspace_id, 'name': self.data_path.name}
        if include_path:
            result['data_path'] = str(self.data_path)
        return result

    def serve_forever(self, poll_interval=0.5):
        self.project_monitor.start()
        self.git_backup_monitor.start()
        try:
            return super().serve_forever(poll_interval)
        finally:
            self.project_monitor.stop()
            self.git_backup_monitor.stop()

    def shutdown(self):
        # Wait for an in-flight capture before acknowledging service shutdown.
        with self.workspace_lock:
            self.stopping = True
            self.project_monitor.stop()
            self.git_backup_monitor.stop()
        return super().shutdown()

    def server_close(self):
        if hasattr(self, 'git_backup_monitor'):
            self.git_backup_monitor.stop()
        if hasattr(self, 'project_monitor'):
            with self.workspace_lock:
                self.project_monitor.stop()
        return super().server_close()

    def assert_selection_current(self):
        if self.installation_file and onboarding.selection_fingerprint(self.installation_file) != self.selection_fingerprint:
            raise onboarding.SetupConflict('The default workspace changed in another process. Restart this server before continuing.', restart_required=True)


class Handler(BaseHTTPRequestHandler):
    server_version = "Mnemos"
    sys_version = ""

    def log_message(self, format, *args):
        # Do not log URLs, query strings, access tokens, or document contents.
        pass

    def _headers(self, status, content_type, size, cookie=None, download=None):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(size))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Content-Security-Policy", "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'none'; form-action 'self'")
        if cookie:
            for item in (cookie if isinstance(cookie, list) else [cookie]):
                self.send_header("Set-Cookie", item)
        if download:
            self.send_header('Content-Disposition', f'attachment; filename="{download}"')
        self.end_headers()

    def _json(self, payload, status=200, cookie=None):
        from .privacy import AUDIENCE, scan
        if status < 300 and AUDIENCE.get() != 'local':
            scan(payload)
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(body), cookie)
        self.wfile.write(body)

    def _guard(self, mutating=False):
        host = self.headers.get("Host", "").lower()
        if host not in self.server.allowed_hosts:
            raise core.MnemosError("Unrecognized host.", 403)
        origin = self.headers.get("Origin")
        if origin:
            parsed = urlsplit(origin)
            if parsed.scheme not in {"http", "https"} or parsed.netloc.lower() != host or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
                raise core.MnemosError("Cross-origin requests are not allowed.", 403)
        if mutating and self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            raise core.MnemosError("Send JSON with Content-Type application/json.", 415)
        if mutating and self.headers.get("Sec-Fetch-Site") == "cross-site":
            raise core.MnemosError("Cross-site requests are not allowed.", 403)

    def _body(self):
        if self.headers.get("Transfer-Encoding"):
            raise core.MnemosError("Chunked request bodies are unsupported.")
        try:
            size = int(self.headers.get("Content-Length", "0"))
        except ValueError as exc:
            raise core.MnemosError("Invalid request size.") from exc
        if size < 0 or size > 1_000_000:
            raise core.MnemosError("Request is too large.", 413)
        try:
            result = json.loads(self.rfile.read(size).decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise core.MnemosError("Request must contain a JSON object.") from exc
        if not isinstance(result, dict):
            raise core.MnemosError("Request must contain a JSON object.")
        return result

    def _local_identity(self, key):
        if (self.server.local_owner and is_loopback(self.client_address[0]) and isinstance(key, str)
                and key and secrets.compare_digest(key, self.server.local_key)):
            owner = core.load_config(self.server.data_path)['owner'] if (self.server.data_path / 'config.json').exists() else 'Local engineer'
            return {'role': 'owner', 'author': owner, 'local': True}
        return None

    def _identity(self):
        authorization = self.headers.get("Authorization")
        if authorization and not (self.server.data_path / "config.json").exists():
            return {"role": "anonymous", "author": ""}
        if authorization:
            if not authorization.startswith("Bearer "):
                return {"role": "anonymous", "author": ""}
            return core.authenticate(self.server.data_path, authorization[7:]) or {"role": "anonymous", "author": ""}
        cookies = SimpleCookie()
        try:
            cookies.load(self.headers.get("Cookie", ""))
        except Exception:
            return {"role": "anonymous", "author": ""}
        if "mnemos_session" in cookies:
            key = cookies["mnemos_session"].value
            with self.server.session_lock:
                session = self.server.sessions.get(key)
                if session and session["expires"] > time.time():
                    return core.authenticate(self.server.data_path, session.get("token", "")) or {"role": "anonymous", "author": ""}
                self.server.sessions.pop(key, None)
            return {"role": "anonymous", "author": ""}
        key = self.headers.get('X-Mnemos-Local-Key', '')
        if not key and self.server.local_cookie in cookies:
            with self.server.session_lock:
                session = self.server.sessions.get(cookies[self.server.local_cookie].value)
                if session and session['expires'] > time.time():
                    key = session.get('local_key', '')
        local = self._local_identity(key)
        if local:
            return local
        return {"role": "anonymous", "author": ""}

    def _require(self, identity, roles):
        if identity["role"] not in roles:
            raise core.MnemosError("Sign in with an account that has permission for this action.", 401 if identity["role"] == "anonymous" else 403)

    def _require_local_setup(self):
        if (not self.server.local_owner or not self.server.setup_enabled
                or not is_loopback(self.client_address[0])):
            raise core.MnemosError('Setup is available only from the local owner launcher.', 403)
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            raise core.MnemosError('Cross-site setup requests are not allowed.', 403)
        if not self._identity().get('local'):
            raise core.MnemosError('Open Mnemos from its local launcher to sign in securely.', 403)

    def _workspace_guard(self, method, parsed):
        markers = [self.headers.get('X-Mnemos-Workspace'), *parse_qs(parsed.query).get('workspace', [])]
        if any(marker is not None and marker != self.server.workspace_id for marker in markers):
            raise onboarding.SetupConflict('The active workspace changed. Reload the library before applying changes or downloading files.')
        browser = self.headers.get('Origin') or self.headers.get('Sec-Fetch-Site')
        local_owner = self.server.local_owner and not self.headers.get('Authorization')
        if method == 'POST' and (browser or local_owner) and not self.headers.get('X-Mnemos-Workspace'):
            raise onboarding.SetupConflict('Reload the library to identify the active workspace before applying changes.')

    def _setup_metadata(self):
        initialized = (self.server.data_path / 'config.json').exists()
        default = self.server.installation_file is not None
        return {'active_workspace': self.server.active_workspace(), 'workspace_id': self.server.workspace_id,
                'service_managed': self.server.launcher_managed,
                'settings_revision': onboarding.settings_revision(self.server.data_path),
                'setup_modes': (['update', 'create', 'select'] if initialized else ['create', 'select']) if default else (['update'] if initialized else ['create']),
                'selection_scope': 'default' if default else 'pinned'}

    def _require_setup_snapshot(self, payload):
        expected = payload.get('expected_workspace')
        if (not isinstance(expected, dict) or expected.get('data_path') != str(self.server.data_path)
                or expected.get('revision') != self.server.workspace_id):
            raise onboarding.SetupConflict('The active workspace changed. Reload setup before applying this choice.')
        if payload.get('expected_settings_revision') != onboarding.settings_revision(self.server.data_path):
            raise onboarding.SetupConflict('The active workspace settings changed. Reload setup before applying this choice.', 'settings_changed')

    def _setup_overview(self):
        # Config writers replace atomically. Pair displayed choices with the
        # exact revision the user reviewed, without creating a lock on GET.
        for _ in range(3):
            before = onboarding.settings_revision(self.server.data_path)
            result = onboarding.choices(self.server.data_path)
            metadata = self._setup_metadata()
            if metadata['settings_revision'] == before:
                return self._json({**result, **metadata})
        raise onboarding.SetupConflict('Workspace settings are changing. Reload setup before continuing.', 'settings_changed')

    def _inspect_setup(self, payload):
        if set(payload) - {'data_path', 'expected_workspace', 'expected_settings_revision'}:
            raise core.MnemosError('Inspect accepts only the selected folder and the current workspace revision.')
        self._require_setup_snapshot(payload)
        target = onboarding.data_directory(payload.get('data_path'))
        before = onboarding.settings_revision(target)
        target, config = onboarding.validate_target(target)
        if config is None:
            raise core.MnemosError('This folder is not an initialized Mnemos workspace. Choose create to initialize a new folder.')
        result = onboarding.choices(target, config)
        if before != onboarding.settings_revision(target):
            raise onboarding.SetupConflict('The selected workspace settings changed during inspection. Inspect it again.', 'settings_changed')
        result['settings_revision'] = before
        return self._json({'workspace': result, **self._setup_metadata()})

    def _apply_setup(self, payload):
        if not self.server.setup_lock.acquire(blocking=False):
            raise core.MnemosError('Another setup request is running. Wait for it to finish.', 409)
        try:
            pointer = self.server.installation_file
            # Serialize competing default servers before checking or changing their pointer.
            with core.storage_lock(pointer.parent) if pointer else nullcontext():
                self.server.assert_selection_current()
                with core.storage_lock(self.server.data_path):
                    self._require_setup_snapshot(payload)
                    mode = payload.get('mode')
                    if mode not in self._setup_metadata()['setup_modes']:
                        raise core.MnemosError('This launch is pinned to a workspace. Use the default launcher to create or select another default workspace.' if not pointer else 'Choose update, create, or select explicitly.')
                    if not pointer and payload.get('data_path', str(self.server.data_path)) != str(self.server.data_path):
                        raise core.MnemosError('This launch is pinned to its data folder. Use the default launcher to select another workspace.')
                    choices = {key: value for key, value in payload.items() if key not in {'expected_workspace', 'expected_settings_revision'}}
                    previous = self.server.active_workspace()
                    was_initialized = (self.server.data_path / 'config.json').exists()
                    selected, result = onboarding.configure(self.server.data_path, choices)
                    switched = selected != self.server.data_path or not was_initialized
                    revision = uuid.uuid4().hex if switched else self.server.workspace_id
                    if pointer and switched:
                        try:
                            onboarding.save_selection(pointer, selected, revision)
                        except (OSError, ValueError) as exc:
                            raise core.MnemosError('Could not save the default workspace selection. The previous workspace remains active; a new folder may have been initialized.', 500) from exc
                        self.server.selection_fingerprint = onboarding.selection_fingerprint(pointer)
                    # No request can cross this activation: _handle holds workspace_lock.
                    self.server.data_path = selected
                    self.server.workspace_id = revision
                    self.server.project_monitor.wake.set()
                    if switched:
                        with self.server.session_lock:
                            self.server.sessions = {k:v for k,v in self.server.sessions.items() if v.get('local_key') == self.server.local_key}
                            self.server.login_failures.clear()
                        result['warnings'].append('Connections that explicitly specify a folder keep using that folder. Reconfigure them separately if you want them to use this workspace.')
                    result.update(self._setup_metadata(), mode=mode, previous_workspace=previous)
                    return self._json(result)
        finally:
            self.server.setup_lock.release()

    def _dispatch(self, method):
        self._guard(method == "POST")
        parsed = urlsplit(self.path)
        path = unquote(parsed.path)
        if path == '/api/local-login' and method == 'POST':
            identity = self._local_identity(self._body().get('key'))
            if not identity:
                raise core.MnemosError('Local access expired. Open Mnemos from its launcher again.', 401)
            session = secrets.token_urlsafe(32)
            with self.server.session_lock:
                self.server.sessions = {k:v for k,v in self.server.sessions.items() if v['expires'] > time.time()}
                self.server.sessions[session] = {'local_key': self.server.local_key, 'expires': time.time() + 43200}
            return self._json({'signed_in': True}, cookie=[f'{self.server.local_cookie}={session}; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200', 'mnemos_session=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0'])
        if path in {'/api/runtime', '/api/runtime/stop'}:
            self._require_local_setup()
            self._workspace_guard(method, parsed)
            if path == '/api/runtime' and method == 'GET':
                return self._json({'kind': 'mnemos-local-runtime-v1', 'managed': self.server.launcher_managed, 'stopping': self.server.stopping,
                                   'installation': str(self.server.installation_file) if self.server.installation_file else None,
                                   'data_path': str(self.server.data_path), 'workspace_id': self.server.workspace_id,
                                   'initialized': (self.server.data_path / 'config.json').exists()})
            if path == '/api/runtime/stop' and method == 'POST':
                self._body()
                if not self.server.launcher_managed:
                    raise core.MnemosError('This server is managed externally. Stop it with the process that started it.', 409)
                self.server.stopping = True
                self._json({'stopping': True})
                threading.Thread(target=self.server.shutdown, daemon=True).start()
                return
        self.server.assert_selection_current()
        if path == '/setup.html' and not self.server.setup_enabled:
            raise core.MnemosError('Setup is available through the local launcher only.', 403)
        if path in {'/api/setup', '/api/setup/inspect'}:
            self._require_local_setup()
        self._workspace_guard(method, parsed)
        # Hold the pointer lock through every mutation, so a competing default
        # server cannot activate another workspace between our check and write.
        if method == 'POST' and path != '/api/setup/inspect' and self.server.installation_file:
            with core.storage_lock(self.server.installation_file.parent):
                self.server.assert_selection_current()
                return self._dispatch_routes(method, parsed, path)
        return self._dispatch_routes(method, parsed, path)

    def _dispatch_routes(self, method, parsed, path):
        from .privacy import audience
        identity = self._identity()
        target = 'local' if identity.get('local') else identity.get('audience', 'ai')
        with audience(target):
            return self._routes(method, parsed, path)

    def _routes(self, method, parsed, path):
        if path.startswith('/api/git-backup'):
            self._require_local_setup()
            from . import git_backup
            data = self.server.data_path
            if path == '/api/git-backup' and method == 'GET':
                return self._json(git_backup.status(data))
            if method == 'POST':
                payload = self._body()
                if path == '/api/git-backup':
                    return self._json(git_backup.configure(data, payload))
                if path == '/api/git-backup/sync':
                    return self._json(git_backup.sync(data, push=payload.get('push') is True))
            raise core.MnemosError('Unsupported Git backup operation.', 405)
        if path == '/api/privacy/check' and method == 'POST':
            self._require_local_setup()
            from . import privacy
            payload = self._body()
            ids = payload.get('ids', [])
            if not isinstance(ids, list) or not ids or len(ids) > 100 or any(not isinstance(i, str) for i in ids):
                raise core.MnemosError('Select source documents to check before sharing.')
            docs = [core.get_document(self.server.data_path, i) for i in ids]
            privacy.require(self.server.data_path, docs)
            expected = payload.get('fingerprints', {})
            if any(expected.get(d['id']) != d['privacy']['fingerprint'] for d in docs):
                raise core.MnemosError('Sources or policies changed. Reload this preview before sharing.', 409)
            privacy.scan(payload.get('content', ''))
            return self._json({'allowed': True})
        if path == '/api/privacy':
            self._require_local_setup()
            from . import privacy
            if method == 'GET':
                return self._json(privacy.overview(self.server.data_path))
            if method == 'POST':
                return self._json(privacy.update(self.server.data_path, self._body()))
        # Only the launcher can manage export artifacts, settings and backups.
        if path.startswith(('/api/skill-', '/api/backups', '/api/export', '/api/settings')):
            self._require_local_setup()
        if path == '/api/knowledge-projects' or path.startswith('/api/knowledge-projects/'):
            self._require_local_setup()
            from . import knowledge_projects
            if method == 'GET':
                if path == '/api/knowledge-projects':
                    return self._json(knowledge_projects.overview(self.server.data_path))
                return self._json(knowledge_projects.detail(self.server.data_path, path.rsplit('/', 1)[1]))
            operations = {'/api/knowledge-projects': knowledge_projects.save,
                          '/api/knowledge-projects/remove': knowledge_projects.remove,
                          '/api/knowledge-projects/analysis': knowledge_projects.analysis,
                          '/api/knowledge-projects/map': knowledge_projects.create_map}
            if method == 'POST' and path in operations:
                return self._json(operations[path](self.server.data_path, self._body()))
            raise core.MnemosError('Project route or method not supported.', 405)
        if path in {'/api/projects', '/api/projects/refresh', '/api/projects/remove', '/api/projects/automatic'}:
            self._require_local_setup()
            from . import projects
            if method == 'GET' and path == '/api/projects':
                return self._json(self.server.project_monitor.overview(projects.list_projects(self.server.data_path)))
            if method == 'POST':
                operation = {'/api/projects': projects.save_project,
                             '/api/projects/refresh': projects.refresh_project,
                             '/api/projects/remove': projects.remove_project,
                             '/api/projects/automatic': projects.set_automatic}[path]
                result = operation(self.server.data_path, self._body())
                self.server.project_monitor.wake.set()
                return self._json(result)
            raise core.MnemosError('Method not supported.', 405)
        if path == '/api/setup/inspect' and method == 'POST':
            return self._inspect_setup(self._body())
        if path == '/api/setup':
            if method == 'GET':
                return self._setup_overview()
            if method == 'POST':
                return self._apply_setup(self._body())
        if path in {'/api/connections', '/api/connections/test'}:
            self._require_local_setup()
            from . import connections
            if method == 'GET' and path == '/api/connections':
                project = parse_qs(parsed.query).get('project', [None])[0]
                return self._json(connections.public_inventory(connections.inventory(self.server.data_path, self.server.connection_checks, project)))
            if method == 'POST' and path == '/api/connections/test':
                payload = self._body()
                if not isinstance(payload.get('client'), str) or (payload.get('project') is not None and not isinstance(payload['project'], str)):
                    raise core.MnemosError('Choose a connection and project folder.')
                return self._json(connections.check_connection(self.server.data_path, self.server.connection_checks, payload['client'], payload.get('project')))
        initialized = (self.server.data_path / 'config.json').exists()
        if not initialized:
            if path.startswith('/api/'):
                self._require_local_setup()
                return self._json({'initialized': False, 'setup_required': True, 'setup_url': '/setup.html',
                                   'workspace_id': self.server.workspace_id}, 409)
            if path == '/':
                path = '/setup.html'
            # Static setup assets can load without reading a nonexistent config.
            identity = {'role': 'owner', 'author': ''}
        else:
            identity = self._identity()
        role, data = identity["role"], self.server.data_path
        if method == "GET" and path == "/api/graph":
            self._require(identity, {"owner", "author", "reader"})
            from . import graph
            return self._json(graph.build(data, role, local=bool(identity.get('local'))))
        if method == "GET" and path == "/api/bootstrap":
            from .knowledge_projects import catalog
            return self._json({"app": {"name": "Mnemos", "version": __version__}, "session": identity,
                               "documents": core.list_documents(data, role),
                               "knowledge_projects": catalog(data, role),
                               "workflows": core.list_workflows(data, role) if role != "anonymous" else [],
                               "settings": core.public_settings(data, role) if identity.get("local") else {},
                               "workspace_id": self.server.workspace_id,
                               "active_workspace": self.server.active_workspace(bool(identity.get('local'))),
                               "setup_available": self.server.setup_enabled and bool(identity.get('local'))})
        if method == "POST" and path == "/api/login":
            payload = self._body()
            with self.server.session_lock:
                failures = [stamp for stamp in self.server.login_failures.get(self.client_address[0], []) if stamp > time.time() - 60]
                self.server.login_failures[self.client_address[0]] = failures
                if len(failures) >= 10:
                    raise core.MnemosError("Too many sign-in attempts. Try again in a minute.", 429)
                token = payload.get("token", "")
                authenticated = core.authenticate(data, token)
                if not authenticated:
                    failures.append(time.time())
                    raise core.MnemosError("That access token is not valid.", 401)
                self.server.login_failures.pop(self.client_address[0], None)
                session = secrets.token_urlsafe(32)
                for key, value in list(self.server.sessions.items()):
                    if value["expires"] <= time.time():
                        del self.server.sessions[key]
                self.server.sessions[session] = {"token": token, "expires": time.time() + 43200}
            secure = "; Secure" if self.headers.get("Origin", "").startswith("https://") else ""
            return self._json({"session": authenticated}, cookie=[f"mnemos_session={session}; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200{secure}", f"{self.server.local_cookie}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"])
        if method == "POST" and path == "/api/logout":
            self._body()
            cookies = SimpleCookie(self.headers.get("Cookie", ""))
            if "mnemos_session" in cookies:
                with self.server.session_lock:
                    self.server.sessions.pop(cookies["mnemos_session"].value, None)
            if self.server.local_cookie in cookies:
                with self.server.session_lock:
                    self.server.sessions.pop(cookies[self.server.local_cookie].value, None)
            return self._json({"ok": True}, cookie=["mnemos_session=logged-out; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200", f"{self.server.local_cookie}=; Path=/; HttpOnly; SameSite=Strict; Max-Age=0"])
        if path.startswith("/api/"):
            self._require(identity, {"owner", "author", "reader"})
        if path == '/api/skill-matches':
            self._require_local_setup()
            from . import skill_matching
            if method == 'POST':return self._json(skill_matching.check(data,self._body()))
            raise core.MnemosError('Unsupported skill matching operation.',405)
        if path == '/api/local-skills':
            self._require_local_setup()
            from . import skill_inventory
            if method=='GET':return self._json(skill_inventory.inventory(data))
            if method=='POST':return self._json(skill_inventory.add_folder(data,self._body()))
            raise core.MnemosError('Unsupported local skill operation.',405)
        if path.startswith('/api/skill-analysis/'):
            self._require(identity, {'owner','author'})
            from . import skill_analysis
            operations={'request':skill_analysis.request,'preview':skill_analysis.validate,'accept':skill_analysis.accept}
            operation=operations.get(path[len('/api/skill-analysis/'):])
            if method=='POST' and operation:return self._json(operation(data,self._body()))
            raise core.MnemosError('Unsupported analysis operation.',405)
        if path in {'/api/skill-candidates','/api/skill-builds','/api/skill-preview'} or path.startswith('/api/skill-builds/'):
            self._require(identity, {'owner','author'})
            from . import skill_builder
            if path == '/api/skill-candidates' and method == 'GET':
                params=parse_qs(parsed.query)
                return self._json(skill_builder.candidates(data,params.get('query',[''])[0],params.get('examples',['0'])[0]=='1', params.get('project_id',[''])[0]))
            if path == '/api/skill-preview' and method == 'POST':
                return self._json(skill_builder.prepare(data,self._body()))
            if path == '/api/skill-builds':
                if method == 'GET':return self._json({'builds':skill_builder.list_builds(data)})
                if method == 'POST':return self._json(skill_builder.save(data,self._body()))
            if path.startswith('/api/skill-builds/') and method == 'GET':
                parts=path[len('/api/skill-builds/'):].split('/')
                built=skill_builder.read(data,parts[0])
                if len(parts)==1:return self._json(built)
                if len(parts)==2 and parts[1] in {'download','handoff'}:
                    zipped=parts[1]=='download'
                    content=skill_builder.archive(built) if zipped else built['handoff'].encode()
                    self._headers(200,'application/zip' if zipped else 'text/markdown; charset=utf-8',len(content),download=built['name']+('.zip' if zipped else '-handoff.md'))
                    self.wfile.write(content)
                    return
            raise core.MnemosError('Skill route or method not supported.',405)
        if method == "GET" and path == "/api/documents":
            query = parse_qs(parsed.query).get("query", [""])[0]
            from .knowledge_projects import scope
            return self._json({"documents": scope(core.list_documents(data, role, query), parse_qs(parsed.query).get("project_id", [""])[0])})
        if method == "GET" and path.startswith("/api/documents/"):
            document = core.get_document(data, path[len("/api/documents/"):], role)
            from .knowledge_projects import freshness
            return self._json({"document": document, "freshness": freshness(data, document)})
        if method == "GET" and path == "/api/recall":
            from .recall import recall
            params = parse_qs(parsed.query)
            try:
                budget = int(params.get("budget", ["6000"])[0])
            except ValueError as exc:
                raise core.MnemosError("Recall budget must be a number of characters.") from exc
            return self._json(recall(data, params.get("query", [""])[0], budget, role, params.get("project_id", [""])[0]))
        if method == 'GET' and path == '/api/handoff':
            from .handoff import build_pack
            params = parse_qs(parsed.query)
            try:
                budget = int(params.get('budget', ['6000'])[0])
            except ValueError as exc:
                raise core.MnemosError('Handoff budget must be a number of characters.') from exc
            return self._json(build_pack(data, params.get('query', [''])[0], budget, role, params.get('id', []), params.get('project_id', [''])[0]))
        if method == 'GET' and path == '/api/skills/export':
            self._require(identity, {'owner', 'author'})
            from .handoff import skills_archive
            content = skills_archive()
            self._headers(200, 'application/zip', len(content), download='mnemos-skills.zip')
            self.wfile.write(content)
            return
        if method == "POST" and path == "/api/documents":
            self._require(identity, {"owner", "author"})
            document = core.save_document(data, self._body(), role, identity["author"])
            return self._json({"document": document})
        if method == "GET" and path.startswith("/api/workflows/") and path.endswith("/plan"):
            workflow_id = path[len("/api/workflows/"):-len("/plan")]
            return self._json(core.workflow_plan(data, workflow_id, role))
        if method == "POST" and path == "/api/settings":
            self._require(identity, {"owner"})
            return self._json({"settings": core.update_settings(data, self._body())})
        if path == "/api/backups":
            self._require(identity, {"owner"})
            from . import backup
            if method == "GET":
                return self._json({"backups": backup.list_backups(data)})
            if method == "POST":
                self._body()
                return self._json({"backup": backup.create_backup(data)})
        if method == "GET" and path == "/api/export":
            self._require(identity, {"owner"})
            from . import export
            content = export.vault_archive(data)
            self._headers(200, "application/zip", len(content))
            self.wfile.write(content)
            return
        if path.startswith("/api/"):
            raise core.MnemosError("API endpoint not found.", 404)
        if method == "GET":
            relative = "index.html" if path == "/" else path.lstrip("/")
            if not relative or any(part.startswith(".") for part in Path(relative).parts):
                raise core.MnemosError("File not found.", 404)
            web = core.ROOT / "web"
            static = core.safe_path(web, relative)
            if not static.is_file() or static.suffix not in {".html", ".js", ".css", ".svg", ".png", ".ico", ".woff2"}:
                raise core.MnemosError("File not found.", 404)
            content = static.read_bytes()
            mime = mimetypes.guess_type(static.name)[0] or "application/octet-stream"
            self._headers(200, mime + ("; charset=utf-8" if mime.startswith("text/") or static.suffix == ".js" else ""), len(content))
            self.wfile.write(content)
            return
        raise core.MnemosError("Method not allowed.", 405)

    def _handle(self, method):
        try:
            with self.server.workspace_lock:
                self._dispatch(method)
        except core.MnemosError as exc:
            payload = {"error": str(exc)}
            if isinstance(exc, onboarding.SetupConflict):
                payload.update(code=exc.code, reload_required=True, restart_required=exc.restart_required)
            self._json(payload, exc.status)
        except ValueError as exc:
            self._json({"error": str(exc)}, 400)
        except (BrokenPipeError, ConnectionResetError):
            pass
        except Exception:
            self._json({"error": "The operation could not be completed. Check the configuration and file permissions."}, 500)

    def do_GET(self):
        self._handle("GET")

    def do_POST(self):
        self._handle("POST")

    def do_OPTIONS(self):
        self._json({"error": "Cross-origin access is not enabled."}, 405)


def serve(data_path, host="127.0.0.1", port=4318, public_hosts=(), require_auth=False, installation_file=None):
    server = MnemosServer((host, port), data_path, public_hosts, require_auth=require_auth, installation_file=installation_file)
    print(f"Mnemos is running at http://{host}:{server.server_address[1]}", flush=True)
    print("Press Ctrl+C to stop. Network access requires tokens and a TLS reverse proxy.", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()

# Compatibility for older local launchers.
KeystoneServer = MnemosServer
