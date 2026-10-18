"""Versioned vault snapshots with checksums; cloud transport uses configured rclone."""
from __future__ import annotations
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
import subprocess
import tempfile
import threading
from datetime import datetime, timezone
import uuid
import zipfile

_LOCK = threading.RLock()
MANIFEST = 'keystone-manifest.json'  # Stable snapshot format, including pre-rename archives.
MAX_RESTORE_BYTES = 2 * 1024 * 1024 * 1024


def _write(path: Path, content: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix='.mnemos-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def snapshot_bytes(vault: Path) -> tuple[bytes, int]:
    """Capture regular vault files only, never dereferencing symlinks."""
    vault = Path(vault)
    if vault.is_symlink() or not vault.is_dir():
        raise ValueError('Vault must be a real directory, not a symlink.')
    manifest = {'format': 1, 'created': datetime.now(timezone.utc).isoformat(), 'files': {}}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as archive:
        for directory, directories, filenames in os.walk(vault, followlinks=False):
            base = Path(directory)
            if any((base / name).is_symlink() for name in directories + filenames):
                raise ValueError('Snapshots refuse symlinks. Remove the linked file or folder first.')
            directories[:] = [name for name in directories if name not in {'.git', '.trash', 'node_modules'}]
            for name in sorted(filenames):
                source = base / name
                if not source.is_file():
                    raise ValueError('Snapshots only support regular files.')
                relative = source.relative_to(vault).as_posix()
                raw = source.read_bytes()
                archive.writestr('vault/' + relative, raw)
                manifest['files'][relative] = {'sha256': hashlib.sha256(raw).hexdigest(), 'size': len(raw)}
        archive.writestr(MANIFEST, json.dumps(manifest, indent=2))
    return buffer.getvalue(), len(manifest['files'])


def list_backups(data_path) -> list[dict]:
    history = Path(data_path) / 'backup-history.json'
    if history.is_symlink():
        raise ValueError('Backup history cannot be a symlink.')
    if not history.exists():
        return []
    content = json.loads(history.read_text())
    if not isinstance(content, list):
        raise ValueError('Backup history is invalid.')
    return content


def _record(data_path, result):
    from .core import storage_lock
    with storage_lock(data_path):
        history = list_backups(data_path)
        history.insert(0, result)
        _write(Path(data_path) / 'backup-history.json', json.dumps(history[:500], indent=2).encode())


def create_backup(data_path) -> dict:
    from .core import load_config, storage_lock, vault_path
    with _LOCK:
        # Share the capture/configuration lock so the snapshot cannot interleave
        # with a Mnemos writer. Release it before potentially slow cloud I/O.
        with storage_lock(data_path):
            config = load_config(data_path)
            vault = vault_path(data_path)
            snapshot, files = snapshot_bytes(vault)
        data_path = Path(data_path).resolve()
        settings = config.get('backup', {})
        provider = settings.get('provider', 'local')
        if provider not in {'local', 'rclone'}:
            raise ValueError('Choose local or rclone backup storage.')
        destination = Path(settings.get('destination') or data_path / 'backups').expanduser().resolve()
        if destination == vault or vault in destination.parents:
            raise ValueError('Backup destination must be outside the vault.')
        remote = settings.get('remote', '').strip()
        if provider == 'rclone':
            if not re.fullmatch(r'[A-Za-z0-9_-]+:[^\x00-\x1f]*', remote):
                raise ValueError('Use a configured rclone remote such as encrypted:mnemos.')
            if '..' in remote.split(':', 1)[1].split('/'):
                raise ValueError('Remote path cannot contain parent traversal.')
            if not shutil.which('rclone'):
                raise ValueError('Install rclone and configure a remote before backing up to cloud storage.')
        stamp = datetime.now(timezone.utc)
        name = 'mnemos-' + stamp.strftime('%Y%m%dT%H%M%S') + '-' + uuid.uuid4().hex[:8] + '.zip'
        destination.mkdir(parents=True, exist_ok=True)
        target = destination / name
        _write(target, snapshot)
        checksum = hashlib.sha256(snapshot).hexdigest()
        _write(target.with_suffix('.zip.sha256'), (checksum + '  ' + name + '\n').encode())
        result = {'id': name[:-4], 'name': name, 'created': stamp.isoformat(), 'provider': provider,
                  'path': str(target), 'size': len(snapshot), 'files': files, 'sha256': checksum,
                  'status': 'complete', 'destination': str(destination), 'encrypted': False}
        if provider == 'rclone':
            remote_file = remote.rstrip('/') + '/' + name
            result['remote'] = remote_file
            result['encryption'] = 'Determined by your rclone remote; use crypt for client-side encryption.'
            try:
                for source in (target, target.with_suffix('.zip.sha256')):
                    subprocess.run(['rclone', 'copyto', str(source), remote.rstrip('/') + '/' + source.name,
                                    '--immutable', '--retries', '2'], check=True, capture_output=True, timeout=300)
            except (subprocess.SubprocessError, OSError) as error:
                result['status'] = 'cloud-failed'
                result['error'] = 'Cloud upload failed. Local snapshot retained; check your rclone configuration.'
                _record(data_path, result)
                raise ValueError(result['error']) from error
        _record(data_path, result)
        return result


def restore_backup(archive_path, destination) -> dict:
    """Verify a complete snapshot, then restore only into an empty destination."""
    archive_path, destination = Path(archive_path), Path(destination).expanduser()
    if destination.is_symlink():
        raise ValueError('Restore destination cannot be a symlink.')
    destination = destination.resolve()
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError('Restore requires a new or empty directory. Existing vaults are never overwritten.')
    records = []
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Snapshot contains duplicate paths.')
        if sum(info.file_size for info in archive.infolist()) > MAX_RESTORE_BYTES:
            raise ValueError('Snapshot exceeds the 2 GiB restore limit.')
        manifest = json.loads(archive.read(MANIFEST))
        if not isinstance(manifest, dict) or manifest.get('format') != 1 or not isinstance(manifest.get('files'), dict):
            raise ValueError('Unsupported snapshot manifest.')
        expected = {MANIFEST}
        for relative, entry in manifest['files'].items():
            if not isinstance(relative, str) or not isinstance(entry, dict) or not isinstance(entry.get('size'), int) or entry['size'] < 0 or not isinstance(entry.get('sha256'), str):
                raise ValueError('Invalid file record in snapshot manifest.')
            path = PurePosixPath(relative)
            if not relative or path.is_absolute() or any(part in {'.', '..', ''} for part in relative.split('/')) or '\\' in relative or ':' in relative:
                raise ValueError('Unsafe path in snapshot.')
            member = 'vault/' + relative
            expected.add(member)
            info = archive.getinfo(member)
            if stat.S_ISLNK(info.external_attr >> 16):
                raise ValueError('Snapshot contains a symlink.')
            raw = archive.read(member)
            if len(raw) != entry['size'] or hashlib.sha256(raw).hexdigest() != entry['sha256']:
                raise ValueError('Snapshot checksum mismatch: ' + relative)
            records.append((relative, raw))
        if set(names) != expected:
            raise ValueError('Snapshot contains files not covered by its manifest.')
    destination.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix='.mnemos-restore-', dir=destination.parent))
    try:
        for relative, raw in records:
            path = staging / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(raw)
        if destination.exists():
            destination.rmdir()
        staging.rename(destination)
    finally:
        if staging.exists():
            shutil.rmtree(staging)
    return {'path': str(destination), 'files': len(records), 'verified': True}
