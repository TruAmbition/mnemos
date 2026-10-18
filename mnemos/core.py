"""Vault operations shared by the CLI and HTTP server. No third-party dependencies.

The vault is always ``data/vault``. Configuration contains token hashes, never tokens.
Markdown uses a deliberately small YAML frontmatter subset: scalar values and lists.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import secrets
import shutil
import tempfile
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

LOCK = threading.RLock()
_LOCK_DEPTH = threading.local()
ROOT = Path(__file__).resolve().parent.parent
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$")
TYPES = {
    "runbook": "Runbooks", "knowledge-item": "Knowledge", "knowledge": "Knowledge",
    "troubleshooting": "Troubleshooting", "decision": "Decisions", "work-log": "Work Logs",
    "micro-task": "Microtasks", "microtask": "Microtasks", "skill": "Skills", "context": "Contexts", "flow": "Flows",
}
STATUSES = {"draft", "verified", "archived"}


class MnemosError(ValueError):
    def __init__(self, message: str, status: int = 400):
        super().__init__(message)
        self.status = status


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def atomic_write(path: Path, content: str | bytes) -> None:
    """Replace a file atomically with owner-only permissions."""
    path = Path(path)
    if path.is_symlink():
        raise MnemosError("Refusing to replace a symbolic link.")
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=".mnemos-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(content.encode("utf-8") if isinstance(content, str) else content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _data_path(data_path: str | Path) -> Path:
    path = Path(data_path).expanduser().absolute()
    if path.is_symlink():
        raise MnemosError("The Mnemos data folder must not be a symbolic link.")
    return path.resolve()


@contextmanager
def storage_lock(data_path: str | Path):
    """Serialize mutations across server threads and CLI processes."""
    with LOCK:
        data = _data_path(data_path)
        data.mkdir(parents=True, exist_ok=True)
        held = getattr(_LOCK_DEPTH, "held", set())
        if str(data) in held:
            yield
            return
        lock_path = data / ".keystone.lock"
        if lock_path.is_symlink():
            raise MnemosError("The storage lock must not be a symbolic link.")
        fd = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            if os.name == "nt":
                import msvcrt
                if os.fstat(fd).st_size == 0:
                    os.write(fd, b"0")
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
            else:
                import fcntl
                fcntl.flock(fd, fcntl.LOCK_EX)
            _LOCK_DEPTH.held = held | {str(data)}
            try:
                yield
            finally:
                _LOCK_DEPTH.held = held
        finally:
            os.close(fd)


def vault_path(data_path: str | Path) -> Path:
    data = _data_path(data_path)
    vault = data / "vault"
    if vault.is_symlink():
        raise MnemosError("The dedicated vault must not be a symbolic link.")
    return vault


def safe_path(base: Path, relative: str | Path) -> Path:
    """Reject traversal and every symlink component inside the dedicated directory."""
    base = Path(base).resolve()
    relative = Path(relative)
    if relative.is_absolute() or ".." in relative.parts:
        raise MnemosError("Path must stay inside the dedicated vault.")
    cursor = base
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            raise MnemosError("Symbolic links are not allowed inside the vault.")
    if not cursor.resolve().is_relative_to(base):
        raise MnemosError("Path escapes the dedicated vault.")
    return cursor


def load_config(data_path: str | Path) -> dict:
    path = _data_path(data_path) / "config.json"
    if path.is_symlink():
        raise MnemosError("Configuration must not be a symbolic link.")
    try:
        config = json.loads(path.read_text("utf-8"))
    except FileNotFoundError as exc:
        raise MnemosError("Initialize Mnemos first with `python -m mnemos init`.") from exc
    except (OSError, json.JSONDecodeError) as exc:
        raise MnemosError("Cannot read Mnemos configuration.") from exc
    if not isinstance(config, dict) or config.get("version") != 1:
        raise MnemosError("Unsupported Mnemos configuration.")
    vault_path(data_path)
    return config


def save_config(data_path: str | Path, config: dict) -> None:
    with storage_lock(data_path):
        atomic_write(_data_path(data_path) / "config.json", json.dumps(config, indent=2) + "\n")


def initialize(data_path: str | Path, author: str = "Local engineer") -> dict:
    """Create a separate vault, or return a previously initialized installation."""
    with storage_lock(data_path):
        data = _data_path(data_path)
        author = str(author).strip()
        if not author or len(author) > 120:
            raise MnemosError("Choose an author name between 1 and 120 characters.")
        if (data / "config.json").exists():
            return load_config(data)
        vault = vault_path(data)
        if vault.exists() and any(vault.iterdir()):
            raise MnemosError("Refusing to use a nonempty vault. Choose a new dedicated data folder.")
        data.mkdir(parents=True, exist_ok=True)
        vault.mkdir(exist_ok=True)
        seed = ROOT / "seed-vault"
        if seed.exists():
            for source in seed.rglob("*"):
                if source.is_symlink():
                    raise MnemosError("Seed vault contains an unsupported symbolic link.")
                target = safe_path(vault, source.relative_to(seed))
                if source.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                else:
                    atomic_write(target, source.read_bytes())
        config = {
            "version": 1, "owner": author, "vault_path": str(vault), "created": now(),
            "backup": {"provider": "local", "destination": str(data / "backups"), "remote": ""},
            "tokens": [],
        }
        save_config(data, config)
        return config


def _scalar(value: str):
    value = value.strip()
    try:
        return json.loads(value)
    except (json.JSONDecodeError, ValueError):
        if value.startswith("[") and value.endswith("]"):
            return [_scalar(item) for item in value[1:-1].split(",") if item.strip()]
        if len(value) >= 2 and value[0] == value[-1] == "'":
            return value[1:-1].replace("''", "'")
        return value


def parse_markdown(text: str) -> tuple[dict, str]:
    """Read basic Obsidian properties, including YAML block lists; do not execute YAML tags."""
    lines = text.replace("\r\n", "\n").split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, text
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        return {}, text
    metadata, last_key = {}, None
    for line in lines[1:end]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if re.match(r"^\s*-\s+", line) and last_key:
            if not isinstance(metadata[last_key], list):
                metadata[last_key] = []
            metadata[last_key].append(_scalar(re.sub(r"^\s*-\s+", "", line)))
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_-]*):\s*(.*)$", line)
        if match:
            last_key, value = match.groups()
            metadata[last_key] = _scalar(value) if value else ""
    return metadata, "\n".join(lines[end + 1:]).lstrip("\n")


def _read_document(path: Path, vault: Path) -> dict:
    raw = path.read_bytes()
    if len(raw) > 1_000_000:
        raise MnemosError(f"Document is too large: {path.name}")
    meta, body = parse_markdown(raw.decode("utf-8"))
    document_id = str(meta.get("id", path.stem))
    if not ID_RE.fullmatch(document_id):
        raise MnemosError(f"Invalid document id in {path.name}.")
    tags = meta.get("tags", [])
    if isinstance(tags, str):
        tags = [item.strip() for item in tags.split(",") if item.strip()]
    if not isinstance(tags, list):
        tags = []
    return {
        "id": document_id, "path": path.relative_to(vault).as_posix(),
        "title": str(meta.get("title", path.stem.replace("-", " ").title())),
        "type": str(meta.get("type", "knowledge-item")),
        "status": str(meta.get("status", "draft")), "project": str(meta.get("project", "General")),
        "tags": [str(tag) for tag in tags], "author": str(meta.get("author", "Unknown")),
        "updated": str(meta.get("updated", "")), "verified": str(meta.get("verified", "")),
        "summary": str(meta.get("summary", "")), "body": body,
        "revision": hashlib.sha256(raw).hexdigest(), "example": meta.get("example", False) is True,
        "sources": meta.get("sources", []) if isinstance(meta.get("sources", []), list) else [],
        "project_id": str(meta.get("project_id", "")),
        "repository_ids": [i for i in meta.get("repository_ids", []) if isinstance(i, str) and ID_RE.fullmatch(i)] if isinstance(meta.get("repository_ids", []), list) else [],
        "related_ids": meta.get("related_ids", []) if isinstance(meta.get("related_ids", []), list) else [],
    }


def list_documents(data_path: str | Path, role: str = "owner", query: str = "") -> list[dict]:
    load_config(data_path)
    vault = vault_path(data_path)
    from .knowledge_projects import annotate, entries
    definitions = entries(data_path)
    repositories = load_config(data_path).get('projects', [])
    documents, seen = [], set()
    if role not in {"owner", "author", "reader"}:
        return []
    for path in sorted(vault.rglob("*.md")):
        safe_path(vault, path.relative_to(vault))
        if any(part.startswith(".") for part in path.relative_to(vault).parts) or path.relative_to(vault).parts[0] == "Templates":
            continue
        document = _read_document(path, vault)
        if document["id"] in seen:
            raise MnemosError(f"Duplicate document id: {document['id']}")
        seen.add(document["id"])
        if role == "reader" and document["status"] != "verified":
            continue
        annotate(data_path, [document], definitions, repositories)
        haystack = " ".join([document["title"], document["body"], document["summary"],
                            document["project"], " ".join(document.get("project_names", [])), " ".join(document["tags"]) ]).casefold()
        terms = query.casefold().split()
        if all(term in haystack for term in terms):
            document["_score"] = sum(5 if term in document["title"].casefold() else 1 for term in terms)
            documents.append(document)
    documents.sort(key=lambda item: (item["_score"], item["updated"], item["title"]), reverse=True)
    for document in documents:
        document.pop("_score", None)
    return documents


def get_document(data_path: str | Path, document_id: str, role: str = "owner") -> dict:
    document = next((item for item in list_documents(data_path, role) if item["id"] == document_id), None)
    if not document:
        raise MnemosError("Document not found.", 404)
    return document


def _text(payload: dict, key: str, default: str, limit: int = 300) -> str:
    value = payload.get(key, default)
    if not isinstance(value, str) or len(value) > limit:
        raise MnemosError(f"{key} must be text of at most {limit} characters.")
    return value.strip() if key != "body" else value


def _related_links(body: str, related_ids: list[str], documents: list[dict], document_id: str) -> str:
    """Refresh only our generated links, leaving the author's own links untouched."""
    start, end = "<!-- mnemos:related:start -->", "<!-- mnemos:related:end -->"
    body = re.sub(re.escape(start) + r".*?" + re.escape(end), "", body, flags=re.S).rstrip()
    indexed = {doc["id"]: doc for doc in documents}
    links = []
    for related_id in dict.fromkeys(related_ids):
        doc = indexed.get(related_id)
        if not doc or related_id == document_id:
            continue  # Preserve unresolved IDs in properties without creating phantom graph nodes.
        target = str(Path(doc["path"]).with_suffix("")).replace("\\", "/")
        if any(char in target for char in "[]|#\n\r"):
            continue
        label = re.sub(r"[\[\]|\n\r]", " ", doc["title"])
        links.append(f"- [[{target}|{label}]]")
    if links:
        body += "\n\n" + start + "\n## Related knowledge\n\n" + "\n".join(links) + "\n" + end
    return body


def save_document(data_path: str | Path, payload: dict, role: str = "owner", author: str | None = None) -> dict:
    if role not in {"owner", "author"}:
        raise MnemosError("Only authors can change documents.", 403)
    if not isinstance(payload, dict):
        raise MnemosError("Document must be a JSON object.")
    with storage_lock(data_path):
        config = load_config(data_path)
        vault = vault_path(data_path)
        title = _text(payload, "title", "", 200)
        if not title:
            raise MnemosError("A document title is required.")
        supplied_id = payload.get("id")
        document_id = supplied_id or (re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:90] or "document") + "-" + secrets.token_hex(3)
        if not isinstance(document_id, str) or not ID_RE.fullmatch(document_id):
            raise MnemosError("Document id may contain letters, numbers, hyphens, and underscores only.")
        documents = list_documents(data_path)
        existing = next((item for item in documents if item["id"] == document_id), None)
        revision = payload.get("revision")
        if existing and revision != existing["revision"]:
            raise MnemosError("This document changed. Reload it before saving your edits.", 409)
        if not existing and revision:
            raise MnemosError("This document no longer exists. Reload before saving.", 409)
        kind = _text(payload, "type", existing["type"] if existing else "knowledge-item", 40)
        if kind not in TYPES:
            raise MnemosError("Unknown document type.")
        if kind == "micro-task":
            kind = "microtask"
        status = _text(payload, "status", "draft", 20)
        if status not in STATUSES:
            raise MnemosError("Status must be draft, verified, or archived.")
        if role != "owner" and status == "verified":
            raise MnemosError("Only the owner can verify documentation.", 403)
        tags = payload.get("tags", [])
        if not isinstance(tags, list) or len(tags) > 40 or any(not isinstance(t, str) or len(t) > 80 for t in tags):
            raise MnemosError("Tags must be a list of up to 40 short strings.")
        body = _text(payload, "body", "", 256_000)
        if re.search(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----", body):
            raise MnemosError("The document contains a private key. Remove credentials before saving.")
        metadata = {
            "id": document_id, "title": title, "type": kind, "status": status,
            "project": _text(payload, "project", "General", 120), "tags": list(dict.fromkeys(tags)),
            "author": author or config["owner"], "updated": now(),
            "verified": now() if status == "verified" else "",
            "summary": _text(payload, "summary", "", 2000), "example": payload.get("example", False) is True,
        }
        project_id = _text(payload, 'project_id', existing.get('project_id', '') if existing else '', 120)
        if project_id and not ID_RE.fullmatch(project_id):
            raise MnemosError('Use a valid top-level project ID.')
        repository_ids = payload.get('repository_ids', existing.get('repository_ids', []) if existing else [])
        if not isinstance(repository_ids, list) or len(repository_ids) > 100 or any(not isinstance(i, str) or not ID_RE.fullmatch(i) for i in repository_ids):
            raise MnemosError('Use up to 100 valid repository IDs.')
        metadata['project_id'] = project_id
        metadata['repository_ids'] = list(dict.fromkeys(repository_ids))
        for key in ("sources", "related_ids"):
            values = payload.get(key, existing.get(key, []) if existing else [])
            if not isinstance(values, list) or len(values) > 100 or any(not isinstance(value, str) or len(value) > 2000 for value in values):
                raise MnemosError(f"{key} must be a list of up to 100 short text references.")
            if key == "related_ids" and any(not ID_RE.fullmatch(value) for value in values):
                raise MnemosError("related_ids must contain valid document ids.")
            metadata[key] = values
        body = _related_links(body, metadata["related_ids"], documents, document_id)
        relative = existing["path"] if existing else f"{TYPES[kind]}/{document_id}.md"
        path = safe_path(vault, relative)
        text = "---\n" + "\n".join(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in metadata.items()) + "\n---\n\n" + body.rstrip() + "\n"
        atomic_write(path, text)
        return _read_document(path, vault)


def issue_token(data_path: str | Path, role: str, author: str) -> str:
    if role not in {"reader", "author", "owner"}:
        raise MnemosError("Unknown access role.")
    if not isinstance(author, str) or not author.strip() or len(author) > 120:
        raise MnemosError("A name of at most 120 characters is required.")
    with storage_lock(data_path):
        config = load_config(data_path)
        token = "kst_" + secrets.token_urlsafe(32)
        config.setdefault("tokens", []).append({
            "hash": hashlib.sha256(token.encode()).hexdigest(), "role": role,
            "author": author.strip(), "created": now(),
        })
        save_config(data_path, config)
        return token


def authenticate(data_path: str | Path, token: str) -> dict | None:
    if not isinstance(token, str) or len(token) > 256:
        return None
    digest = hashlib.sha256(token.encode()).hexdigest()
    for identity in load_config(data_path).get("tokens", []):
        if hmac.compare_digest(digest, identity.get("hash", "")):
            return {"role": identity["role"], "author": identity["author"]}
    return None


def list_workflows(data_path: str | Path, role: str = "owner") -> list[dict]:
    if role not in {"owner", "author", "reader"}:
        return []
    vault = vault_path(data_path)
    directory = safe_path(vault, "Workflows")
    visible = {item["id"] for item in list_documents(data_path, role)}
    workflows, seen = [], set()
    for path in sorted(directory.glob("*.json")):
        safe_path(vault, path.relative_to(vault))
        try:
            raw = json.loads(path.read_text("utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise MnemosError(f"Invalid workflow file: {path.name}") from exc
        if not isinstance(raw, dict) or not ID_RE.fullmatch(str(raw.get("id", ""))):
            raise MnemosError(f"Workflow requires a valid id: {path.name}")
        if raw["id"] in seen:
            raise MnemosError(f"Duplicate workflow id: {raw['id']}")
        seen.add(raw["id"])
        steps = raw.get("steps", [])
        if not isinstance(steps, list) or len(steps) > 250 or any(not isinstance(step, dict) for step in steps):
            raise MnemosError(f"Workflow steps must be objects: {path.name}")
        if any(not isinstance(step.get("document_id"), str) for step in steps):
            raise MnemosError(f"Workflow document references must be document ids: {path.name}")
        if role == "reader" and (raw.get("status") != "verified" or any(s.get("document_id") not in visible for s in steps)):
            continue
        workflows.append({
            "id": raw["id"], "title": str(raw.get("title", raw["id"])),
            "description": str(raw.get("description", "")), "status": str(raw.get("status", "draft")),
            "steps": [{"id": step.get("id"), "title": str(step.get("title", step.get("id", ""))),
                       "document_id": step.get("document_id"), "depends_on": step.get("depends_on", []),
                       "requires_approval": step.get("requires_approval", True) is not False} for step in steps],
        })
    return workflows


def workflow_plan(data_path: str | Path, workflow_id: str, role: str = "owner") -> dict:
    workflow = next((item for item in list_workflows(data_path, role) if item["id"] == workflow_id), None)
    if not workflow:
        raise MnemosError("Workflow not found.", 404)
    documents = {item["id"]: item for item in list_documents(data_path, role)}
    indexed = {}
    for step in workflow["steps"]:
        if not isinstance(step["id"], str) or not ID_RE.fullmatch(step["id"]):
            raise MnemosError("Each workflow step requires a valid id.")
        if step["id"] in indexed:
            raise MnemosError("Workflow contains duplicate step ids.")
        if step["document_id"] not in documents:
            raise MnemosError(f"Step {step['id']} references missing or inaccessible documentation.")
        deps = step["depends_on"]
        if not isinstance(deps, list) or any(not isinstance(dep, str) for dep in deps):
            raise MnemosError("Step dependencies must be a list of step ids.")
        indexed[step["id"]] = step
    ordered, active, visited = [], set(), set()
    def visit(step_id: str) -> None:
        if step_id not in indexed:
            raise MnemosError(f"Unknown workflow dependency: {step_id}")
        if step_id in active:
            raise MnemosError("Workflow contains a dependency cycle.")
        if step_id in visited:
            return
        active.add(step_id)
        for dependency in indexed[step_id]["depends_on"]:
            visit(dependency)
        active.remove(step_id)
        visited.add(step_id)
        step = dict(indexed[step_id])
        step["document"] = documents[step["document_id"]]
        ordered.append(step)
    for step_id in indexed:
        visit(step_id)
    return {"id": workflow["id"], "title": workflow["title"], "status": workflow["status"],
            "steps": ordered, "execution": "plan-only", "valid": True,
            "warnings": [f"Step {step['id']} uses example or unverified documentation; verify it in the target environment."
                         for step in ordered if step["document"]["status"] != "verified" or step["document"]["example"]]}


def obsidian_installed() -> bool:
    return bool(shutil.which("obsidian") or Path("/Applications/Obsidian.app").exists()
                or (Path.home() / "Applications/Obsidian.app").exists()
                or (Path(os.environ.get("LOCALAPPDATA", "/nonexistent")) / "Obsidian/Obsidian.exe").exists())


def public_settings(data_path: str | Path, role: str) -> dict:
    if role != "owner":
        return {}
    config = load_config(data_path)
    return {"vault_path": str(vault_path(data_path)), "backup": config.get("backup", {}),
            "obsidian_installed": obsidian_installed()}


def update_settings(data_path: str | Path, payload: dict) -> dict:
    backup = payload.get("backup")
    if not isinstance(backup, dict) or backup.get("provider") not in {"local", "rclone"}:
        raise MnemosError("Choose local or rclone backup storage.")
    destination = _text(backup, "destination", "", 4096)
    remote = _text(backup, "remote", "", 1024)
    if backup["provider"] == "local" and not destination:
        raise MnemosError("Choose a local backup folder.")
    if backup["provider"] == "rclone" and not re.fullmatch(r"[A-Za-z0-9_-]+:[^\x00-\x1f]*", remote):
        raise MnemosError("Cloud backup needs an existing rclone remote, for example drive:Mnemos.")
    if backup["provider"] == "rclone" and ".." in remote.split(":", 1)[1].split("/"):
        raise MnemosError("Cloud backup paths cannot contain parent traversal.")
    if backup["provider"] == "local":
        target = Path(destination).expanduser().resolve()
        if target.is_relative_to(vault_path(data_path).resolve()):
            raise MnemosError("Store backups outside the vault.")
        destination = str(target)
    with storage_lock(data_path):
        config = load_config(data_path)
        config["backup"] = {"provider": backup["provider"], "destination": destination, "remote": remote}
        save_config(data_path, config)
    return public_settings(data_path, "owner")

# Compatibility for older local integrations.
KeystoneError = MnemosError
