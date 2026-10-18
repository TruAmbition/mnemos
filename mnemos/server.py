"""Small same-origin web server. Deploy behind TLS for access beyond localhost."""
from __future__ import annotations

import ipaddress
import json
import mimetypes
import secrets
import threading
import time
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

from . import __version__, core


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
        self.data_path = Path(data_path).expanduser().resolve()
        bound_loopback = is_loopback(address[0])
        self.local_owner = bound_loopback and not require_auth
        self.setup_enabled = self.local_owner and not public_hosts
        self.installation_file = Path(installation_file) if installation_file else None
        self.setup_lock = threading.Lock()
        if (self.data_path / 'config.json').exists():
            core.load_config(self.data_path)
        elif not self.setup_enabled:
            raise core.MnemosError('Initialize the installation locally before enabling network or authenticated access.')
        if not bound_loopback and not public_hosts:
            raise core.MnemosError("Network sharing requires --public-host with the hostname readers will use.")
        self.sessions, self.login_failures = {}, {}
        self.session_lock = threading.RLock()
        super().__init__(address, handler or Handler)
        port = self.server_address[1]
        local_names = ["localhost", "127.0.0.1", "[::1]"] if bound_loopback else []
        self.allowed_hosts = {f"{name}:{port}" for name in local_names}
        if port == 80:
            self.allowed_hosts.update(local_names)
        for name in public_hosts:
            if "/" in name or "@" in name or "\n" in name or "\r" in name:
                self.server_close()
                raise core.MnemosError("--public-host must be a hostname, optionally including its port.")
            self.allowed_hosts.add(name.lower())


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
            self.send_header("Set-Cookie", cookie)
        if download:
            self.send_header('Content-Disposition', f'attachment; filename="{download}"')
        self.end_headers()

    def _json(self, payload, status=200, cookie=None):
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

    def _identity(self):
        authorization = self.headers.get("Authorization")
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
                    return core.authenticate(self.server.data_path, session["token"]) or {"role": "anonymous", "author": ""}
                self.server.sessions.pop(key, None)
            return {"role": "anonymous", "author": ""}
        if self.server.local_owner and is_loopback(self.client_address[0]):
            return {"role": "owner", "author": core.load_config(self.server.data_path)["owner"]}
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
        if (self.server.data_path / 'config.json').exists():
            self._require(self._identity(), {'owner'})
        elif self.headers.get('Authorization'):
            raise core.MnemosError('Initialize this local installation without a shared access token.', 403)

    def _dispatch(self, method):
        self._guard(method == "POST")
        parsed = urlsplit(self.path)
        path = unquote(parsed.path)
        if path in {'/api/setup', '/setup.html'}:
            self._require_local_setup()
        if path == '/api/setup':
            from . import onboarding
            if method == 'GET':
                return self._json(onboarding.choices(self.server.data_path))
            if method == 'POST':
                payload = self._body()
                if not self.server.setup_lock.acquire(blocking=False):
                    raise core.MnemosError('Another setup request is running. Wait for it to finish.', 409)
                try:
                    selected, result = onboarding.configure(self.server.data_path, payload)
                    if self.server.installation_file:
                        onboarding.save_selection(self.server.installation_file, selected)
                    # Switch only after validated settings and the launch selection are saved.
                    self.server.data_path = selected
                    with self.server.session_lock:
                        self.server.sessions.clear()
                        self.server.login_failures.clear()
                    return self._json(result)
                finally:
                    self.server.setup_lock.release()
        initialized = (self.server.data_path / 'config.json').exists()
        if not initialized:
            if path.startswith('/api/'):
                return self._json({'initialized': False, 'setup_required': True, 'setup_url': '/setup.html'}, 409)
            if path == '/':
                path = '/setup.html'
            # Static setup assets can load without reading a nonexistent config.
            identity = {'role': 'owner', 'author': ''}
        else:
            identity = self._identity()
        role, data = identity["role"], self.server.data_path
        if method == "GET" and path == "/api/bootstrap":
            return self._json({"app": {"name": "Mnemos", "version": __version__}, "session": identity,
                               "documents": core.list_documents(data, role),
                               "workflows": core.list_workflows(data, role) if role != "anonymous" else [],
                               "settings": core.public_settings(data, role),
                               "setup_available": self.server.setup_enabled and self.server.local_owner and role == 'owner'})
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
            return self._json({"session": authenticated}, cookie=f"mnemos_session={session}; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200{secure}")
        if method == "POST" and path == "/api/logout":
            self._body()
            cookies = SimpleCookie(self.headers.get("Cookie", ""))
            if "mnemos_session" in cookies:
                with self.server.session_lock:
                    self.server.sessions.pop(cookies["mnemos_session"].value, None)
            return self._json({"ok": True}, cookie="mnemos_session=logged-out; Path=/; HttpOnly; SameSite=Strict; Max-Age=43200")
        if path.startswith("/api/"):
            self._require(identity, {"owner", "author", "reader"})
        if method == "GET" and path == "/api/documents":
            from urllib.parse import parse_qs
            query = parse_qs(parsed.query).get("query", [""])[0]
            return self._json({"documents": core.list_documents(data, role, query)})
        if method == "GET" and path.startswith("/api/documents/"):
            return self._json({"document": core.get_document(data, path[len("/api/documents/"):], role)})
        if method == "GET" and path == "/api/recall":
            from urllib.parse import parse_qs
            from .recall import recall
            params = parse_qs(parsed.query)
            try:
                budget = int(params.get("budget", ["6000"])[0])
            except ValueError as exc:
                raise core.MnemosError("Recall budget must be a number of characters.") from exc
            return self._json(recall(data, params.get("query", [""])[0], budget, role))
        if method == 'GET' and path == '/api/handoff':
            from urllib.parse import parse_qs
            from .handoff import build_pack
            params = parse_qs(parsed.query)
            try:
                budget = int(params.get('budget', ['6000'])[0])
            except ValueError as exc:
                raise core.MnemosError('Handoff budget must be a number of characters.') from exc
            return self._json(build_pack(data, params.get('query', [''])[0], budget, role, params.get('id', [])))
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
            self._dispatch(method)
        except core.MnemosError as exc:
            self._json({"error": str(exc)}, exc.status)
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


def serve(data_path, host="127.0.0.1", port=4318, public_hosts=(), require_auth=False):
    server = MnemosServer((host, port), data_path, public_hosts, require_auth=require_auth)
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
