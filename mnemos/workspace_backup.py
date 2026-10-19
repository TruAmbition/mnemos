"""Complete, local workspace recovery with reviewed paths and no credential restore."""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import stat
import tempfile
import uuid
import zipfile
from . import core, privacy

FORMAT = 'mnemos-workspace-backup-v1'
MANIFEST = 'mnemos-workspace.json'
FOLDERS = ('vault', 'skill-builds', 'skill-analysis', 'skill-proposals', 'session-inbox')
LIMIT = 512 * 1024 * 1024
EXCLUDED = {'Credentials and connection profiles', 'AI sharing approvals', 'Git history',
            'Personal Obsidian settings and plugins', 'Search index and model files',
            'External repository contents and installed skills', 'Earlier backup archives'}
PROJECT_FIELDS = ('id', 'name', 'path', 'created', 'updated', 'include', 'exclude', 'responsibility', 'last_refresh')


def portable_config(config):
    projects = config.get('projects', [])
    if (not isinstance(projects, list) or len(projects) > 100
            or any(not isinstance(p, dict) or not core.ID_RE.fullmatch(str(p.get('id', '')))
                   or any(not isinstance(p.get(k), str) for k in ('name', 'path')) for p in projects)):
        raise core.MnemosError('Archive repository registrations are invalid.')
    return {'version': 1, 'owner': config['owner'], 'created': config.get('created', core.now()),
            'projects': [{k: p[k] for k in PROJECT_FIELDS if k in p} for p in projects],
            'skill_folders': config.get('skill_folders', []), 'assistant_mode': 'local', 'tokens': [],
            'semantic_search': {'enabled': False, 'model': config.get('semantic_search', {}).get('model', 'embeddinggemma')}}


def _allowed(name):
    p = PurePosixPath(name)
    if ('\\' in name or ':' in name or p.is_absolute() or '..' in p.parts or not p.parts
            or name != p.as_posix() or any(part.startswith('.') or part.rstrip(' .') != part
                or part.split('.')[0].upper() in {'CON','PRN','AUX','NUL', *('COM'+str(i) for i in range(1,10)), *('LPT'+str(i) for i in range(1,10))}
                for part in p.parts)):
        return False
    return name == 'config.json' or (p.parts[0] in FOLDERS and len(p.parts) > 1
        and (p.parts[0] == 'vault' or (len(p.parts) == 2 and p.suffix == '.json')))


def create(data, payload):
    from . import backup
    target = payload.get('destination', '')
    if not isinstance(target, str) or not Path(target).expanduser().is_absolute():
        raise core.MnemosError('Choose an absolute local folder for workspace backups.')
    target = Path(target).expanduser().absolute()
    if any(p.is_symlink() for p in (target, *target.parents)):
        raise core.MnemosError('Choose a backup folder without symbolic links.')
    data = core._data_path(data)
    if target == data or any(target.is_relative_to(data / f) for f in FOLDERS):
        raise core.MnemosError('Store the archive outside workspace content folders.')
    with core.storage_lock(data):
        files = {'config.json': json.dumps(portable_config(core.load_config(data)), indent=2).encode()}
        total = len(files['config.json'])
        for folder in FOLDERS:
            base = core.safe_path(data, folder)
            for root, dirs, names in os.walk(base, followlinks=False):
                for name in dirs + names:
                    if (Path(root)/name).is_symlink():
                        raise core.MnemosError('Workspace backups refuse symbolic links.')
                dirs[:] = [d for d in dirs if not d.startswith('.') and d not in {'node_modules', '__pycache__'}]
                for name in names:
                    path = Path(root)/name
                    relative = path.relative_to(data).as_posix()
                    if not _allowed(relative):
                        if folder == 'vault' and not name.startswith('.'):
                            raise core.MnemosError('A vault filename is not portable. Rename it before making a complete workspace backup: '+relative)
                        continue
                    if not stat.S_ISREG(path.stat().st_mode):
                        raise core.MnemosError('Only regular files can be backed up.')
                    total += path.stat().st_size
                    if total > LIMIT or len(files) >= 20000:
                        raise core.MnemosError('Workspace backup exceeds 512 MB or 20,000 files.')
                    files[relative] = path.read_bytes()
        if len({name.casefold() for name in files}) != len(files):
            raise core.MnemosError('Rename files that differ only by case before creating a portable workspace backup.')
        manifest = {'format': FORMAT, 'created': core.now(), 'excluded': sorted(EXCLUDED),
                    'files': {n: {'size': len(b), 'sha256': hashlib.sha256(b).hexdigest()} for n,b in files.items()}}
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, 'w', zipfile.ZIP_DEFLATED) as archive:
            for name, raw in files.items():
                archive.writestr(name, raw)
            archive.writestr(MANIFEST, json.dumps(manifest))
        raw = stream.getvalue()
        if len(raw) > LIMIT:
            raise core.MnemosError('The compressed workspace archive exceeds 512 MB.')
        name = 'mnemos-workspace-'+core.now().replace(':', '-')+'-'+uuid.uuid4().hex[:8]+'.zip'
        path = target / name
        core.atomic_write(path, raw)
        sha = hashlib.sha256(raw).hexdigest()
        core.atomic_write(path.with_suffix('.zip.sha256'), sha+'  '+name+'\n')
        result = {'id': uuid.uuid4().hex, 'name': name, 'created': manifest['created'], 'provider': 'local',
                  'path': str(path), 'size': len(raw), 'files': len(files), 'sha256': sha, 'status': 'complete',
                  'scope': 'workspace', 'encrypted': False, 'excluded': sorted(EXCLUDED)}
        backup._record(data, result)
        return result


def _read(value):
    if not isinstance(value, str) or not Path(value).expanduser().is_absolute():
        raise core.MnemosError('Choose an absolute path to a workspace backup ZIP.')
    path = Path(value).expanduser()
    if any(p.is_symlink() for p in (path, *path.parents)) or not path.is_file() or path.stat().st_size > LIMIT:
        raise core.MnemosError('Use a regular workspace archive of at most 512 MB.')
    raw = path.read_bytes()
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            if (len(infos) > 20001 or len({i.filename.casefold() for i in infos}) != len(infos)
                    or sum(i.file_size for i in infos) > LIMIT or any(stat.S_ISLNK(i.external_attr >> 16) for i in infos)):
                raise ValueError('Archive size or duplicate entries')
            manifest = json.loads(archive.read(MANIFEST))
            if manifest.get('format') != FORMAT or not isinstance(manifest.get('files'), dict):
                raise ValueError('Format')
            if set(manifest['files']) | {MANIFEST} != {i.filename for i in infos}:
                raise ValueError('Manifest coverage')
            files = {}
            for name, info in manifest['files'].items():
                entry = archive.getinfo(name)
                if not _allowed(name) or stat.S_ISLNK(entry.external_attr >> 16):
                    raise ValueError('Unsafe path')
                content = archive.read(name)
                if len(content) != info['size'] or hashlib.sha256(content).hexdigest() != info['sha256']:
                    raise ValueError('Checksum')
                files[name] = content
            config = json.loads(files['config.json'])
            if config.get('version') != 1 or not isinstance(config.get('owner'), str):
                raise ValueError('Configuration')
            portable_config(config)
        return files, config, hashlib.sha256(raw).hexdigest()
    except (ValueError, KeyError, TypeError, zipfile.BadZipFile, RuntimeError, OSError) as exc:
        raise core.MnemosError('Archive verification failed. Use an intact Mnemos workspace backup; vault-only ZIPs use the separate vault restore command.') from exc


def preview(data, payload):
    from .onboarding import data_directory
    files, config, sha = _read(payload.get('archive'))
    destination = data_directory(payload.get('destination', ''))
    if destination == Path(data).resolve() or destination.is_relative_to(Path(data).resolve()):
        raise core.MnemosError('Restore into a separate new workspace folder.')
    if destination.exists() and any(destination.iterdir()):
        raise core.MnemosError('Restore requires a new or empty folder. Existing workspaces are never overwritten.')
    mappings = payload.get('repository_paths', {})
    if not isinstance(mappings, dict) or any(not isinstance(v, str) for v in mappings.values()):
        raise core.MnemosError('Repository mappings must contain local paths.')
    projects = config.get('projects', [])
    if set(mappings) - {p['id'] for p in projects}:
        raise core.MnemosError('A repository mapping refers to an unknown registration.')
    from .projects import _root
    repositories = []
    for p in projects:
        chosen = mappings.get(p['id'], p['path'])
        if p['id'] in mappings and chosen:
            chosen = str(_root(chosen))
        repositories.append({'id': p['id'], 'name': p['name'], 'original_path': p['path'],
                             'path': chosen, 'available': bool(chosen and Path(chosen).is_dir())})
    review = {'archive': payload['archive'], 'destination': str(destination), 'sha256': sha,
              'repository_paths': mappings, 'files': len(files), 'repositories': repositories,
              'excluded': sorted(EXCLUDED),
              'notice': 'Recovery stays inactive. Reconnect repositories and external skill folders, configure backups and assistants, and approve AI sharing again. Automatic refresh, pushes, and meaning search start off.'}
    return {**review, 'review_revision': privacy.digest(review)}


def restore(data, payload):
    review = preview(data, payload)
    if payload.get('review_revision') != review['review_revision']:
        raise core.MnemosError('Review the current archive, destination, and path mappings before restoring.', 409)
    files, source, sha = _read(payload['archive'])
    if sha != review['sha256']:
        raise core.MnemosError('Archive changed after preview.', 409)
    destination = Path(review['destination'])
    config = portable_config(source)
    config.update(vault_path=str(destination/'vault'), backup={'provider': 'local', 'destination': str(destination/'backups'), 'remote': ''}, skill_folders=[])
    mapped = {p['id']: p for p in review['repositories']}
    for project in config['projects']:
        project.update(path=mapped[project['id']]['path'], auto_refresh=False)
    files['config.json'] = json.dumps(config, indent=2).encode()
    files['recovery.json'] = json.dumps({'restored': core.now(), 'sha256': sha,
        'external_skill_folders_to_reconnect': source.get('skill_folders', []), 'notice': review['notice']}, indent=2).encode()
    destination.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.mnemos-recovery-', dir=destination.parent))
    try:
        for name, content in files.items():
            core.atomic_write(core.safe_path(stage, name), content)
        (stage/'vault').mkdir(exist_ok=True)
        core.load_config(stage)
        core.list_documents(stage)  # Reject malformed notes/policies before activating anything.
        if destination.exists():
            destination.rmdir()  # Fails if another process populated the target.
        stage.rename(destination)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    return {'path': str(destination), 'files': len(files), 'verified': True, 'active': False, 'notice': review['notice']}
