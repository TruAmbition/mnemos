"""Opt-in documentation Git backups. Never operates on engineering checkouts."""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import threading
from urllib.parse import urlsplit

from . import core, privacy

BRANCH = 'mnemos-backup'
MANIFEST = '.mnemos-backup.json'
INTERVAL = 300
LOCK = threading.RLock()
EXCLUDED = {'.git', '.obsidian', '.trash', '.mnemos-access', 'node_modules', '__pycache__', '.DS_Store', '.gitattributes', '.gitmodules', '.gitignore'}


def _git(repo, *args, input=None, check=True, index=None):
    env = {k: v for k, v in os.environ.items() if not k.startswith('GIT_')}
    env.update(GIT_TERMINAL_PROMPT='0', GIT_OPTIONAL_LOCKS='0', GIT_CONFIG_NOSYSTEM='1',
               GIT_SSH_COMMAND='ssh -oBatchMode=yes -oStrictHostKeyChecking=yes',
               GIT_AUTHOR_NAME='Mnemos backup', GIT_AUTHOR_EMAIL='backup@mnemos.local',
               GIT_COMMITTER_NAME='Mnemos backup', GIT_COMMITTER_EMAIL='backup@mnemos.local')
    if index: env['GIT_INDEX_FILE'] = str(index)
    try:
        result = subprocess.run(['git', '-c', 'core.hooksPath=' + os.devnull, '-c', 'core.fsmonitor=false', '-c', 'core.attributesFile=' + os.devnull,
                                 '-c', 'protocol.ext.allow=never', '-c', 'protocol.file.allow=never',
                                 '-C', str(repo), *args], input=input, capture_output=True, env=env, timeout=60)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise core.MnemosError('Git could not complete. Check Git installation, network access, and existing Git credentials.') from exc
    if check and result.returncode:
        # Git errors can include credentials, URLs and private paths. Never relay them.
        raise core.MnemosError('Git operation failed. Check repository access and Git authentication. No force push or automatic merge was attempted.')
    return result


def _text(repo, *args, **kwargs):
    return _git(repo, *args, **kwargs).stdout.decode('utf-8').strip()


def _owner(data):
    return hashlib.sha256(str(Path(data).resolve()).encode()).hexdigest()


def _path(value):
    p = Path(str(value)).expanduser()
    if not p.is_absolute(): raise core.MnemosError('Choose an absolute folder path.')
    if any(c.is_symlink() for c in [p, *p.parents]):
        raise core.MnemosError('Git backup paths cannot contain symbolic links.')
    return p.resolve()


def _remote(value):
    value = str(value).strip()
    if not value or len(value) > 2048 or any(ord(c) < 33 for c in value):
        raise core.MnemosError('Enter a Git remote URL, without passwords or access tokens.')
    if re.fullmatch(r'[A-Za-z0-9_.-]+@[A-Za-z0-9.-]+:[A-Za-z0-9_./~-]+', value): return value
    parsed = urlsplit(value)
    if parsed.scheme not in {'https', 'ssh'} or not parsed.hostname or parsed.password or parsed.query or parsed.fragment:
        raise core.MnemosError('Use an HTTPS or SSH Git remote. Keep credentials in your Git credential manager.')
    if parsed.scheme == 'https' and parsed.username:
        raise core.MnemosError('Do not put credentials in the Git remote URL.')
    return value


def _files(data):
    vault = core.vault_path(data); result = {}; total = 0
    for folder, dirs, names in os.walk(vault, followlinks=False):
        base = Path(folder)
        dirs[:] = sorted(d for d in dirs if d not in EXCLUDED)
        for name in dirs + names:
            if name in EXCLUDED: continue
            path = base / name
            if path.is_symlink(): raise core.MnemosError('Git backup refuses symlinks in the vault.')
        for name in sorted(names):
            if name in EXCLUDED or name == '.env' or name.startswith('.env.'):
                continue
            path = base / name
            if not path.is_file(): raise core.MnemosError('Git backup supports regular files only.')
            relative = path.relative_to(vault).as_posix()
            if any(ord(c) < 32 for c in relative) or '\\' in relative:
                raise core.MnemosError('A vault filename is not portable to Git backup.')
            if path.stat().st_size > 25_000_000:
                raise core.MnemosError('A vault file exceeds the 25 MB Git backup limit. Use snapshot backups for large attachments.')
            raw = path.read_bytes(); total += len(raw)
            if total > 250_000_000 or len(result) >= 10000:
                raise core.MnemosError('The vault exceeds the Git backup size limit. Use snapshot backups.')
            result['vault/' + relative] = raw
    return result


def _digest(files):
    return privacy.digest({p: hashlib.sha256(b).hexdigest() for p, b in sorted(files.items())})


def _state(data):
    path = core.safe_path(Path(data), 'git-backup-state.json')
    return json.loads(path.read_text()) if path.exists() else {}


def _save_state(data, value):
    core.atomic_write(core.safe_path(Path(data), 'git-backup-state.json'), json.dumps(value, indent=2))


def _head(repo):
    result = _git(repo, 'rev-parse', '--verify', 'HEAD', check=False)
    return result.stdout.decode().strip() if result.returncode == 0 else ''


def _tree(repo, ref):
    entries = {}
    for line in _git(repo, 'ls-tree', '-rz', ref).stdout.split(b'\0'):
        if not line: continue
        header, name = line.split(b'\t', 1)
        mode, kind, oid = header.decode().split()
        if mode != '100644' or kind != 'blob':
            raise core.MnemosError('Backup history contains unsupported links, file modes, or submodules.')
        entries[name.decode('utf-8')] = oid
    return entries


def _manifest(repo, ref='HEAD'):
    try: return json.loads(_text(repo, 'show', ref + ':' + MANIFEST))
    except (ValueError, core.MnemosError) as exc:
        raise core.MnemosError('Use an empty dedicated repository or one created by Mnemos for this workspace.') from exc


def _validate(data, repo, setting=None):
    repo = _path(repo)
    base = Path(data).resolve()
    if repo == base or repo in base.parents or base in repo.parents:
        raise core.MnemosError('Keep the backup repository separate from the Mnemos data folder.')
    if not repo.is_dir() or not (repo / '.git').is_dir() or (repo / '.git').is_symlink():
        raise core.MnemosError('Choose a standalone local Git repository, not a worktree, submodule, or ordinary folder.')
    if Path(_text(repo, 'rev-parse', '--show-toplevel')).resolve() != repo:
        raise core.MnemosError('Select the root of the dedicated documentation repository.')
    if (repo / '.git/objects/info/alternates').exists() or (repo / '.git/shallow').exists():
        raise core.MnemosError('Use a complete standalone repository without shared object storage.')
    if _text(repo, 'symbolic-ref', '--short', 'HEAD') != BRANCH:
        if _head(repo): raise core.MnemosError('Switch this dedicated repository to the mnemos-backup branch.')
    if any(p.name not in {'.git', MANIFEST, 'vault'} for p in repo.iterdir()):
        raise core.MnemosError('Use a dedicated empty repository. Existing project files are never overwritten.')
    if (repo / '.git/info/attributes').exists() and (repo / '.git/info/attributes').stat().st_size:
        raise core.MnemosError('Remove custom Git attributes from the dedicated backup repository.')
    for folder, directories, files in os.walk(repo / 'vault', followlinks=False):
        if any((Path(folder) / name).is_symlink() or name == '.gitattributes' for name in directories + files):
            raise core.MnemosError('Backup checkout contains a link or custom Git attributes. Manual files are not overwritten.')
    if (repo / 'vault').is_symlink():
        raise core.MnemosError('Backup checkout cannot link to another vault.')
    if _text(repo, 'status', '--porcelain', '--untracked-files=all', '--ignored'):
        raise core.MnemosError('The backup checkout has manual changes or extra files. Commit elsewhere or move them before continuing; Mnemos will not overwrite them.')
    head = _head(repo)
    if head:
        record = _manifest(repo)
        names = _tree(repo, 'HEAD')
        if set(names) != set(record.get('files', {})) | {MANIFEST}:
            raise core.MnemosError('The backup branch includes unmanaged files. Use a dedicated repository.')
        if record.get('format') != 1 or record.get('workspace') != _owner(data):
            raise core.MnemosError('This repository belongs to another workspace. Choose a new empty repository.')
    if setting and setting.get('remote'):
        current = _text(repo, 'remote', 'get-url', '--push', '--all', 'origin')
        if current != setting['remote']:
            raise core.MnemosError('Git origin changed. Review and save the remote setting again before pushing.')
    return repo


def configure(data, payload):
    with core.storage_lock(data), LOCK:
        config = core.load_config(data)
        if payload.get('enabled') is False:
            config['git_backup'] = {**config.get('git_backup', {}), 'enabled': False, 'automatic': False, 'auto_push': False}
            core.save_config(data, config)
            return status(data)
        for key in ['automatic', 'auto_push', 'share_history']:
            if key in payload and not isinstance(payload[key], bool): raise core.MnemosError('Choose on or off for Git backup options.')
        remote = _remote(payload['remote']) if payload.get('remote') else ''
        if payload.get('auto_push') and (not remote or payload.get('share_history') is not True):
            raise core.MnemosError('Automatic push requires a remote and acknowledgement that the full Git history will be uploaded.')
        if payload.get('create'):
            parent = _path(payload.get('parent', ''))
            name = str(payload.get('folder', 'mnemos-docs')).strip()
            if not parent.is_dir() or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,79}', name) or name in {'.', '..'}:
                raise core.MnemosError('Choose an existing parent folder and a simple new folder name.')
            repo = parent / name
            if repo.exists(): raise core.MnemosError('That folder already exists. Choose it as an existing repository or enter a new folder name.')
            base = Path(data).resolve()
            if repo == base or base in repo.parents or repo in base.parents:
                raise core.MnemosError('Create the backup repository outside the Mnemos data folder.')
            repo.mkdir(mode=0o700)
            _git(repo, 'init', '-b', BRANCH)
        else:
            repo = _path(payload.get('path', ''))
        repo = _validate(data, repo)
        if not _head(repo): _git(repo, 'symbolic-ref', 'HEAD', 'refs/heads/' + BRANCH)
        current = _text(repo, 'remote')
        if remote:
            if 'origin' in current.splitlines(): _git(repo, 'remote', 'set-url', 'origin', remote)
            else: _git(repo, 'remote', 'add', 'origin', remote)
            # Reject pushurl overrides rather than silently pushing somewhere else.
            if _text(repo, 'remote', 'get-url', '--push', '--all', 'origin') != remote:
                raise core.MnemosError('Origin has a separate push URL. Remove that override in Git before saving.')
        settings = {'enabled': True, 'path': str(repo), 'remote': remote,
                    'automatic': payload.get('automatic', False) or payload.get('auto_push', False),
                    'auto_push': payload.get('auto_push', False), 'share_history': payload.get('share_history', False)}
        config['git_backup'] = settings
        core.save_config(data, config)
        _save_state(data, {})  # Saving a destination never claims that it has been pushed.
        return status(data)


def status(data):
    settings = core.load_config(data).get('git_backup', {})
    result = {'settings': settings, 'color': 'red', 'state': 'off', 'label': 'Local only — no Git remote backup', 'interval_seconds': INTERVAL}
    if not settings.get('enabled'): return result
    state = _state(data)
    result.update(last_commit=state.get('last_commit'), last_push=state.get('last_push'), commit=state.get('commit'))
    try:
        repo = _validate(data, settings.get('path', ''), settings)
        result['color'] = 'amber'
        digest = _digest(_files(data)); head = _head(repo)
        if state.get('error'):
            result.update(state='error', color='red', label=state['error'])
        elif not head or state.get('digest') != digest or state.get('commit') != head:
            result.update(state='pending', label='Documentation changes need a Git backup')
        elif not settings.get('remote'):
            result.update(state='local', label='Committed locally — no Git remote configured')
        elif state.get('pushed_commit') == head and state.get('pushed_remote') == settings['remote']:
            result.update(state='pushed', color='green', label='Latest documentation pushed to Git remote')
        else:
            result.update(state='pending', label='Committed locally — remote push needed')
    except (core.MnemosError, OSError, ValueError) as exc:
        result.update(state='error', color='red', label=str(exc) if isinstance(exc, core.MnemosError) else 'Cannot inspect the documentation backup. Check its folder and permissions.')
    return result


def _commit(data, repo, files, old_head, eligible):
    record = {'format': 1, 'workspace': _owner(data), 'digest': _digest(files), 'remote_eligible': eligible,
              'files': {name: hashlib.sha256(raw).hexdigest() for name, raw in files.items()}}
    contents = {**files, MANIFEST: json.dumps(record, sort_keys=True, indent=2).encode()}
    # Build a separate index directly: no clean filters, attributes, hooks, signing, or unrelated staged files.
    with tempfile.TemporaryDirectory(prefix='mnemos-git-') as temp:
        index = Path(temp) / 'index'
        for name, raw in sorted(contents.items()):
            oid = _text(repo, 'hash-object', '-w', '--stdin', input=raw)
            _git(repo, 'update-index', '--add', '--cacheinfo', '100644', oid, name, index=index)
        tree = _text(repo, 'write-tree', index=index)
        args = ['commit-tree', tree, '-m', 'Back up Mnemos documentation']
        if old_head: args += ['-p', old_head]
        commit = _text(repo, *args)
    _validate(data, repo)
    if _head(repo) != old_head:
        raise core.MnemosError('The backup branch changed during capture. Try again after Git finishes.')
    previous = _manifest(repo).get('files', {}) if old_head else {}
    _git(repo, 'update-ref', 'refs/heads/' + BRANCH, commit, old_head or '0' * len(commit))
    # Only overwrite our previously verified clean dedicated checkout. Write bytes without smudge filters.
    for name in set(previous) - set(files):
        core.safe_path(repo, name).unlink()
    for name, raw in contents.items():
        target = core.safe_path(repo, name); target.parent.mkdir(parents=True, exist_ok=True); core.atomic_write(target, raw)
    _git(repo, 'read-tree', commit)
    return commit


def _history_safe(data, repo, files):
    privacy.full_export(data, included_paths={p[6:] for p in files})
    revisions = _text(repo, 'rev-list', '--max-count=1001', 'HEAD').splitlines()
    if len(revisions) > 1000:
        raise core.MnemosError('This backup has more than 1,000 commits. Start a fresh dedicated backup repository before remote sharing.')
    checked = {}; total = 0
    for ref in revisions:
        record = _manifest(repo, ref)
        if record.get('workspace') != _owner(data) or record.get('remote_eligible') is not True:
            raise core.MnemosError('History contains a local-only snapshot. Keep it local and create a fresh backup repository for remote sharing.')
        names = _tree(repo, ref)
        if set(names) != set(record.get('files', {})) | {MANIFEST} or not set(record['files']).issubset(files):
            raise core.MnemosError('History includes removed or unclassified files. Keep it local and create a fresh repository for remote sharing.')
        for name in record['files']:
            oid = names[name]
            if oid not in checked:
                size = int(_text(repo, 'cat-file', '-s', oid)); total += size
                if size > 25_000_000 or total > 250_000_000:
                    raise core.MnemosError('History exceeds the 250 MB screening limit. Keep it local and create a fresh repository.')
                raw = _git(repo, 'cat-file', 'blob', oid).stdout
                try: privacy.scan(raw.decode('utf-8'))
                except UnicodeDecodeError as exc: raise core.MnemosError('Binary history cannot be screened for secrets. Use a local backup.') from exc
                checked[oid] = hashlib.sha256(raw).hexdigest()
            if checked[oid] != record['files'][name]:
                raise core.MnemosError('Backup history was modified outside Mnemos. Remote sharing is blocked.')



def sync(data, push=False):
    with core.storage_lock(data), LOCK:
        settings = core.load_config(data).get('git_backup', {})
        if not settings.get('enabled'): raise core.MnemosError('Configure the documentation Git repository first.')
        state = _state(data)
        try:
            repo = _validate(data, settings['path'], settings)
            files = _files(data); digest = _digest(files); head = _head(repo)
            eligible = True
            try: privacy.full_export(data, included_paths={p[6:] for p in files})
            except core.MnemosError: eligible = False
            if not head or _manifest(repo).get('digest') != digest:
                head = _commit(data, repo, files, head, eligible)
                state.update(last_commit=core.now())
            state.update(commit=head, digest=digest, error='')
            _save_state(data, state)
            if push:
                if not settings.get('remote') or not settings.get('share_history'):
                    raise core.MnemosError('Save a Git remote and acknowledge full-history sharing before pushing.')
                _history_safe(data, repo, files)
                # Explicit branch and destination, no tags, mirrors, force pushes, pull, or merges.
                _git(repo, 'push', '--no-verify', '--no-follow-tags', settings['remote'], 'HEAD:refs/heads/' + BRANCH)
                state.update(last_push=core.now(), pushed_commit=head, pushed_remote=settings['remote'])
                _save_state(data, state)
        except Exception as exc:
            state['error'] = str(exc) if isinstance(exc, core.MnemosError) else 'Git backup did not complete. Check the repository and file permissions.'
            _save_state(data, state)
            raise core.MnemosError(state['error']) from exc
        return status(data)


class GitBackupMonitor:
    def __init__(self, server):
        self.server = server; self.stopped = threading.Event(); self.thread = None

    def start(self):
        if self.server.setup_enabled and self.thread is None:
            self.thread = threading.Thread(target=self._run, name='mnemos-git-backup', daemon=True); self.thread.start()

    def stop(self): self.stopped.set()

    def _run(self):
        while not self.stopped.is_set():
            self.scan_once()
            self.stopped.wait(INTERVAL)

    def scan_once(self):
        server = self.server
        with server.workspace_lock:
            if self.stopped.is_set() or server.stopping or not server.setup_enabled: return
            try:
                server.assert_selection_current()
                if not (server.data_path / 'config.json').exists(): return
                settings = core.load_config(server.data_path).get('git_backup', {})
                if settings.get('enabled') and settings.get('automatic'):
                    info = status(server.data_path)
                    if info['state'] != 'pushed' or not settings.get('auto_push'):
                        sync(server.data_path, push=settings.get('auto_push', False))
            except Exception:
                # sync persists a safe actionable error; never log Git output or credentials.
                pass
