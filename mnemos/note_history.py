"""Private, content-addressed checkpoints; restoring always creates a new draft."""
from __future__ import annotations
import difflib
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from . import core, privacy

FOLDER = 'note-history'


def _path(data, identifier, revision):
    if (not isinstance(identifier, str) or not core.ID_RE.fullmatch(identifier)
            or not isinstance(revision, str) or not re.fullmatch('[a-f0-9]{64}', revision)):
        raise core.MnemosError('Choose a valid note and saved revision.')
    return core.safe_path(Path(data), f'{FOLDER}/{identifier}--{revision}.json')


def checkpoint(data, identifier, relative, raw, origin='observed'):
    """Save once per byte revision. Never follow history-directory symlinks."""
    revision = hashlib.sha256(raw).hexdigest()
    path = _path(data, identifier, revision)
    if path.exists():
        return
    with core.storage_lock(data):
        if not path.exists():
            core.atomic_write(path, json.dumps({'id': identifier, 'revision': revision,
                'path': relative, 'captured': datetime.now(timezone.utc).isoformat(), 'origin': origin,
                'markdown': raw.decode('utf-8')}, ensure_ascii=False))


def _read(data, identifier, revision):
    path = _path(data, identifier, revision)
    try:
        if path.stat().st_size > 6_000_000:
            raise ValueError()
        value = json.loads(path.read_text('utf-8'))
        if (not isinstance(value, dict) or value.get('id') != identifier or value.get('revision') != revision
                or not isinstance(value.get('markdown'), str)
                or hashlib.sha256(value['markdown'].encode()).hexdigest() != revision):
            raise ValueError()
        core.safe_path(core.vault_path(data), value['path'])
        return value
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise core.MnemosError('This history checkpoint is missing or damaged.', 404) from exc


def overview(data, identifier=''):
    with core.storage_lock(data):
        docs = {d['id']: d for d in core.list_documents(data)}  # Checkpoint observed Obsidian edits.
        if identifier and (not isinstance(identifier, str) or not core.ID_RE.fullmatch(identifier)):
            raise core.MnemosError('Choose a valid note ID.')
        folder = core.safe_path(Path(data), FOLDER)
        versions = []
        for path in folder.glob((identifier + '--' if identifier else '*--') + '*.json'):
            key, revision = path.stem.rsplit('--', 1)
            record = _read(data, key, revision)
            meta, _ = core.parse_markdown(record['markdown'])
            versions.append({k: record[k] for k in ('id', 'revision', 'captured', 'origin')})
            versions[-1].update(title=str(meta.get('title', key)), status=str(meta.get('status', 'draft')),
                current=docs.get(key, {}).get('revision') == revision, missing=key not in docs)
        return {'versions': sorted(versions, key=lambda v: (v['captured'], v['revision']), reverse=True),
            'notice': 'History starts when this version of Mnemos observes a note. App saves are captured; external edits are captured when the library is read. Unobserved edits cannot be recovered. History is private and included only in complete workspace backups.'}


def preview(data, payload):
    with core.storage_lock(data):
        docs = core.list_documents(data)
        record = _read(data, payload.get('id'), payload.get('revision'))
        current = next((d for d in docs if d['id'] == record['id']), None)
        old, body = core.parse_markdown(record['markdown'])
        fields = {k: old[k] for k in ('title', 'type', 'project', 'tags', 'summary', 'example',
                  'project_id', 'repository_ids', 'sources', 'related_ids') if k in old}
        fields.update(id=record['id'], title=str(old.get('title', record['id'])), body=body, status='draft')
        if current:
            fields['revision'] = current['revision']
        binding = {'id': record['id'], 'revision': record['revision'],
                   'current_revision': current['revision'] if current else '', 'draft': fields, 'metadata': old}
        current_text = core.safe_path(core.vault_path(data), current['path']).read_text('utf-8') if current else ''
        diff = ''.join(difflib.unified_diff(current_text.splitlines(True), record['markdown'].splitlines(True),
                                          fromfile='Current note', tofile='Selected historical version'))
        return {**binding, 'review_revision': privacy.digest(binding), 'diff': diff,
                'title': fields['title'], 'captured': record['captured'],
                'notice': 'Restore the selected content as a new draft. Verification and AI approvals do not carry over. Current content remains in history. The diff shows the historical file; save refreshes author/date and generated related links.'}


def restore(data, payload):
    with core.storage_lock(data):
        checked = preview(data, payload)
        if payload.get('review_revision') != checked['review_revision']:
            raise core.MnemosError('The current note or selected version changed. Preview the restore again.', 409)
        saved = core.save_document(data, checked['draft'], extra_metadata=checked['metadata'])
        return {'document': saved, 'notice': 'Restored as a draft. Review before verifying or sharing.'}
