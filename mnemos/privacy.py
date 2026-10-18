"""Fail-closed sharing policy. This controls Mnemos, not direct filesystem access."""
from contextlib import contextmanager
from contextvars import ContextVar
import hashlib
import json
import re
from pathlib import Path
from . import core

AUDIENCE = ContextVar('mnemos_audience', default='local')
MODES = {
    'local': {'label': 'Local only', 'description': 'Keep in the local library and local backups. Block assistant connections, AI handoffs, generated skill exports, team readers, and cloud backups.'},
    'reviewed-ai': {'label': 'Allow reviewed AI sharing', 'description': 'Keep team access blocked. A local owner must approve each note version before assistant access, AI handoffs, or skill exports. Changes to notes, sources, or policy require a new approval.'},
    'team': {'label': 'Approved for team sharing', 'description': 'Allow workspace members to access this content; readers still see verified notes only. AI sharing still requires approval of each note version. This does not publish anything or grant public access.'},
}
RANK = {name: index for index, name in enumerate(MODES)}


@contextmanager
def audience(value):
    token = AUDIENCE.set(value)
    try:
        yield
    finally:
        AUDIENCE.reset(token)


def _read(path):
    if not path.exists():
        return {}
    try:
        if path.stat().st_size > 4_000_000:
            raise ValueError()
        value = json.loads(path.read_text())
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (ValueError, OSError) as exc:
        raise core.MnemosError('Privacy records are invalid. Sharing is blocked until they are restored.') from exc


def _policy_path(data):
    return core.safe_path(core.vault_path(data), 'Projects/privacy.json')


def _approvals_path(data):
    return core.safe_path(Path(data), 'privacy-approvals.json')


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def scan(value):
    """Inspect every string independently so JSON escaping cannot hide assignments."""
    from .projects import SECRET
    extra = re.compile(r'\b(?:github_pat_[A-Za-z0-9_]{20,}|xox[baprs]-[A-Za-z0-9-]{12,}|AIza[A-Za-z0-9_-]{30,}|Bearer\s+[A-Za-z0-9._~+/-]{20,})|(?:^\s*[\"\']?(?:[\w-]*(?:password|passwd|secret|token|api[_-]?key)[\w-]*)[\"\']?\s*[:=]\s*[\"\']?[^\s\"\']{8,})', re.I | re.M)
    def strings(item):
        if isinstance(item, str):
            yield item
        elif isinstance(item, dict):
            for key, val in item.items():
                if isinstance(val, str):
                    yield str(key) + '=' + val
                yield str(key)
                yield from strings(val)
        elif isinstance(item, (list, tuple)):
            for val in item:
                yield from strings(val)
    if any(SECRET.search(text) or extra.search(text) for text in strings(value)):
        raise core.MnemosError('Sharing blocked: possible credentials were detected. Remove them from the source and review again. Secret checks are best effort.', 403)


def describe(data, documents):
    """Resolve provenance transitively, including cycles, without relaxing any source."""
    from .knowledge_projects import entries
    groups = {p['id']: p for p in entries(data)}
    records = _read(_policy_path(data))
    approvals = _read(_approvals_path(data))
    indexed = {d['id']: d for d in documents}
    repositories = {p['id']: p for p in core.load_config(data).get('projects', [])}
    result = {}
    for root in documents:
        pending, seen, evidence, policies = [root['id']], set(), [], []
        while pending:
            identifier = pending.pop()
            if identifier in seen:
                continue
            seen.add(identifier)
            doc = indexed.get(identifier)
            if doc is None:
                policies.append('local'); evidence.append(['missing', identifier]); continue
            record = records.get(identifier, {})
            if not isinstance(record, dict):
                raise core.MnemosError('Invalid privacy record. Sharing is blocked.')
            project_ids = set(doc.get('project_ids', [])) | set(record.get('project_ids', []))
            if doc.get('project_id'):
                project_ids.add(doc['project_id'])
            refs = set(doc.get('related_ids', [])) | set(record.get('source_ids', []))
            refs.update(s[7:].split('@', 1)[0] for s in doc.get('sources', []) if isinstance(s, str) and s.startswith('mnemos:'))
            # Wikilinks can include embedded source text through Obsidian.
            for link in re.findall(r'\[\[([^\]|#]+)(?:[^\]]*)\]\]', doc.get('body', '')):
                target = next((d['id'] for d in documents if link in {d['id'], d['path'], d['path'].removesuffix('.md')}), None)
                if target:
                    refs.add(target)
            project_ids.update(s[15:].split('@', 1)[0] for s in doc.get('sources', []) if isinstance(s, str) and s.startswith('mnemos-project:'))
            repo_ids = set(doc.get('repository_ids', []))
            repo_ids.update(s[4:].split('@', 1)[0] for s in doc.get('sources', []) if isinstance(s, str) and s.startswith('git:project-'))
            for pid in sorted(project_ids):
                group = groups.get(pid)
                policy = (group or {}).get('privacy', 'local')
                policies.append(policy if policy in MODES else 'local')
                evidence.append(['project', pid, digest(group)])
                repo_ids.update((group or {}).get('repository_ids', []))
            for rid in sorted(repo_ids):
                evidence.append(['repository', rid, repositories.get(rid, {}).get('last_refresh', {})])
            if record.get('mode'):
                policies.append(record['mode'] if record['mode'] in MODES else 'local')
            if not project_ids and not refs and not record.get('mode'):
                policies.append('local')
            evidence.append(['note', identifier, doc['revision'], record])
            pending.extend(refs)
        mode = min(policies, key=lambda p: RANK[p]) if policies else 'local'
        fingerprint = digest(sorted(evidence, key=lambda row: (row[0], row[1])))
        approved = mode != 'local' and approvals.get(root['id']) == fingerprint
        result[root['id']] = {'mode': mode, 'label': MODES[mode]['label'], 'fingerprint': fingerprint,
                              'ai_approved': approved, 'source_count': len(seen)}
    return result


def apply(data, documents, role='owner'):
    policies = describe(data, documents)
    target = AUDIENCE.get()
    if role == 'reader' and target == 'local':
        target = 'team'
    visible = []
    for doc in documents:
        policy = policies[doc['id']]
        doc['privacy'] = policy
        if target == 'team' and policy['mode'] != 'team':
            continue
        if target == 'ai' and not policy['ai_approved']:
            continue
        if target != 'local':
            try:
                scan(doc)
            except core.MnemosError:
                continue
        if role == 'reader' and doc['status'] != 'verified':
            continue
        visible.append(doc)
    return visible


def require(data, documents, target='ai'):
    with audience('local'):
        all_docs = core.list_documents(data)
    indexed = {d['id']: d for d in all_docs}
    for doc in documents:
        current = indexed.get(doc['id'])
        if not current or current['revision'] != doc['revision']:
            raise core.MnemosError('Sources changed or are missing. Refresh and review before sharing.', 409)
        policy = current['privacy']
        if target == 'team' and policy['mode'] != 'team' or target == 'ai' and not policy['ai_approved']:
            raise core.MnemosError('Sharing blocked by privacy settings. Open Privacy & sharing locally to review policies and approve current note versions.', 403)
    scan(documents)


def remember_memberships(data):
    """Removing a grouping must never silently release historical captured content."""
    with audience('local'):
        docs = core.list_documents(data)
    records = _read(_policy_path(data))
    for doc in docs:
        if doc.get('project_ids'):
            record = records.setdefault(doc['id'], {})
            record['project_ids'] = sorted(set(record.get('project_ids', [])) | set(doc['project_ids']))
    core.atomic_write(_policy_path(data), json.dumps(records, indent=2))


def overview(data):
    with audience('local'):
        docs = core.list_documents(data)
    return {'modes': MODES, 'documents': docs,
            'notice': 'Approvals allow connected assistants and exports to read the approved version until revoked or its evidence changes. Local files and backups remain readable by your OS account. External copies cannot be recalled.'}


def update(data, payload):
    with core.storage_lock(data), audience('local'):
        doc = core.get_document(data, payload.get('id'))
        if payload.get('fingerprint') != doc['privacy']['fingerprint']:
            raise core.MnemosError('Content, sources, or privacy changed. Review the current version again.', 409)
        operation = payload.get('operation')
        if operation == 'policy':
            mode = payload.get('mode')
            if mode not in MODES:
                raise core.MnemosError('Choose a supported privacy setting.')
            if doc.get('project_ids'):
                raise core.MnemosError('Set privacy on the top-level project. Shared sources retain the strictest project policy.')
            records = _read(_policy_path(data))
            records.setdefault(doc['id'], {})['mode'] = mode
            core.atomic_write(_policy_path(data), json.dumps(records, indent=2))
        elif operation in {'approve', 'revoke'}:
            approvals = _read(_approvals_path(data))
            if operation == 'approve':
                if payload.get('reviewed') is not True or doc['privacy']['mode'] == 'local':
                    raise core.MnemosError('Choose a sharing policy and explicitly confirm review first.', 403)
                scan(doc)
                approvals[doc['id']] = doc['privacy']['fingerprint']
            else:
                approvals.pop(doc['id'], None)
            core.atomic_write(_approvals_path(data), json.dumps(approvals, indent=2))
        else:
            raise core.MnemosError('Choose policy, approve, or revoke.')
        return {'updated': doc['id']}


def full_export(data, *, included_paths=None):
    """Full vault bundles cannot selectively omit maps, attachments, or definitions."""
    from .knowledge_projects import entries
    with audience('local'):
        docs = core.list_documents(data)
    if any(p.get('privacy', 'local') != 'team' for p in entries(data)):
        raise core.MnemosError('Full vault export and cloud backup require every project to allow team sharing. Use local backup to preserve private content.', 403)
    require(data, docs, 'team')
    known_notes = {d['path'] for d in docs}
    known_ids = {d['id'] for d in docs}
    for path in core.vault_path(data).rglob('*'):
        if path.is_file():
            core.safe_path(core.vault_path(data), path.relative_to(core.vault_path(data)))
            relative = path.relative_to(core.vault_path(data)).as_posix()
            if included_paths is not None and relative not in included_paths:
                continue
            known = relative in known_notes or relative in {'Projects/projects.json', 'Projects/privacy.json'}
            if relative.startswith('Maps/') and path.suffix == '.canvas' and path.stem in known_ids:
                canvas = json.loads(path.read_text())
                known = all(n.get('type') != 'file' or n.get('file') in known_notes for n in canvas.get('nodes', []))
            if relative.startswith('Workflows/') and path.suffix == '.json':
                workflow = json.loads(path.read_text())
                known = bool(workflow.get('steps')) and all(s.get('document_id') in known_ids for s in workflow['steps'])
            seed = core.safe_path(core.ROOT / 'seed-vault', relative)
            if seed.is_file() and seed.read_bytes() == path.read_bytes():
                known = True
            if not known:
                raise core.MnemosError('Full export blocked: an attachment or extra vault file has no reviewed sharing classification. Use a local backup instead.', 403)
            # Unknown binary attachments cannot be credential-scanned reliably.
            try:
                scan(path.read_text('utf-8'))
            except UnicodeDecodeError as exc:
                raise core.MnemosError('Full export blocked: a binary attachment cannot be checked. Use a local backup instead.', 403) from exc
