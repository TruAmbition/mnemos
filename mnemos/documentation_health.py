"""Explainable local review queue. No inference, auto-verification, or silent dismissal."""
from __future__ import annotations
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import re
from . import core, privacy

CATEGORIES = {'changed-evidence': 'Changed source evidence', 'unverified': 'Unverified procedure',
              'review-due': 'Verification review due', 'open-questions': 'Open questions', 'skill-review': 'Skill needs review'}
PROCEDURES = {'runbook', 'troubleshooting', 'microtask', 'micro-task', 'flow', 'skill'}


def _date(value):
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed
    except (ValueError, AttributeError, TypeError):
        return None


def _state(data):
    path = core.safe_path(Path(data), 'health-state/state.json')
    if not path.exists():
        return {}
    try:
        value = json.loads(path.read_text('utf-8'))
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (OSError, ValueError) as exc:
        raise core.MnemosError('Health review settings are damaged. Restore from a workspace backup.') from exc


def _questions(body):
    """Only explicit markers and populated questions sections; not AI inference."""
    body = re.sub(r'```.*?```|~~~.*?~~~', '', body, flags=re.S)
    body = re.sub(r'<!--.*?-->', '', body, flags=re.S)
    findings = []
    in_questions = False
    for line in body.splitlines():
        heading = re.match(r'^#{1,6}\s+(.+)', line)
        if heading:
            in_questions = bool(re.fullmatch(r'(?:open questions|unknowns|unresolved issues|gaps and uncertainties)', heading[1].strip(), re.I))
            continue
        text = line.strip().lstrip('-* ').strip()
        if (re.match(r'^\s*[-*]\s+\[ \]\s+\S', line) or re.search(r'\b(?:TODO|FIXME|TBD)\b', line)
                or in_questions and text and text.casefold().rstrip('.:') not in {'none', 'n/a', 'not applicable', 'resolved', 'no open questions'}):
            findings.append(text[:240])
    return list(dict.fromkeys(findings))[:5]


def overview(data, project_id=''):
    from .knowledge_projects import entries, scope, freshness
    from .recall import current_project_context
    from .skill_builder import list_builds, read as read_build
    with core.storage_lock(data):
        config = core.load_config(data)
        days = config.get('documentation_health', {}).get('review_days', 90)
        if type(days) is not int or not 1 <= days <= 730:
            days = 90
        docs = core.list_documents(data)
        indexed = {d['id']: d for d in docs}
        snapshot = (indexed, {p['id']: p for p in entries(data)}, {p['id']: p for p in config.get('projects', [])})
        docs = [d for d in scope(current_project_context(data, docs), project_id) if d['status'] != 'archived' and not d['example']]
        state, items = _state(data), []
        instant = datetime.now(timezone.utc)

        def add(identifier, category, title, reason, revision, projects, target, priority):
            key = identifier + ':' + category
            fingerprint = privacy.digest([revision, reason])
            postponed = state.get(key, {})
            until = _date(postponed.get('until')) if isinstance(postponed, dict) else None
            snoozed = bool(until and until > instant and postponed.get('fingerprint') == fingerprint)
            items.append({'id': key, 'category': category, 'label': CATEGORIES[category], 'title': title,
                'reason': reason, 'fingerprint': fingerprint, 'project_ids': projects, 'target': target,
                'priority': priority, 'snoozed': snoozed, 'until': until.isoformat() if snoozed else ''})

        for doc in docs:
            def note(category, reason, priority=2):
                add(doc['id'], category, doc['title'], reason, doc['privacy']['fingerprint'], doc.get('project_ids', []),
                    {'kind': 'document', 'id': doc['id']}, priority)
            changed = freshness(data, doc, snapshot=snapshot)['changed']
            if changed:
                note('changed-evidence', 'Cited evidence changed or is unavailable: ' + ', '.join(changed) + '. Compare the sources and update the note.', 1)
            if doc['type'] in PROCEDURES and doc['status'] != 'verified':
                note('unverified', 'This ' + doc['type'] + ' is a draft. Check its prerequisites, steps, expected results, and rollback before marking it verified.')
            if doc['status'] == 'verified':
                verified = _date(doc['verified'])
                if not verified or (instant - verified).total_seconds() >= days * 86400:
                    note('review-due', 'Last verification: ' + (doc['verified'] or 'not recorded') +
                        '. Review interval: ' + str(days) + ' days. Age is a review reminder, not proof that the note is wrong.', 3)
            questions = _questions(doc['body'])
            if questions:
                note('open-questions', 'Explicit unfinished items: ' + ' • '.join(questions), 3)
        for built in list_builds(data):
            record = read_build(data, built['id'], for_export=False)
            sources = record.get('candidate', {}).get('sources', [])
            if any(s.get('example') for s in sources):
                continue
            projects = sorted({p for s in sources for p in indexed.get(s.get('id'), s).get('project_ids', [])})
            if project_id and project_id not in projects:
                continue
            stale = built['freshness'] != 'current' or any(
                s.get('id') in indexed and freshness(data, indexed[s['id']], snapshot=snapshot)['changed'] for s in sources)
            unverified = built['readiness'] != 'verified-sources'
            if stale or unverified:
                reason = ('The saved skill’s sources changed or are missing. Review and rebuild the package.' if stale else
                          'The saved skill includes unverified evidence. Validate its source procedures before reuse.')
                add(built['id'], 'skill-review', built['name'], reason,
                    privacy.digest([sources, built, [indexed.get(s.get('id'), {}).get('privacy') for s in sources]]), projects,
                    {'kind': 'skill', 'id': built['id'], 'source_ids': [s['id'] for s in sources if s.get('id') in indexed]}, 1 if stale else 2)
        items.sort(key=lambda i: (i['snoozed'], i['priority'], i['title'].casefold(), i['id']))
        return {'items': items, 'categories': CATEGORIES, 'review_days': days,
            'counts': {category: sum(i['category'] == category and not i['snoozed'] for i in items) for category in CATEGORIES},
            'notice': 'Checks current non-example notes and saved skills against captured evidence. Does not inspect live remote code or prove correctness. Review each finding; snoozing never verifies a note.'}


def configure(data, payload):
    days = payload.get('review_days')
    if type(days) is not int or not 1 <= days <= 730:
        raise core.MnemosError('Choose a review interval between 1 and 730 days.')
    with core.storage_lock(data):
        config = core.load_config(data)
        config['documentation_health'] = {'review_days': days}
        core.save_config(data, config)
    return {'review_days': days}


def snooze(data, payload):
    days = payload.get('days')
    if type(days) is not int or days not in {0, 7, 30}:
        raise core.MnemosError('Choose review now, 7 days, or 30 days.')
    with core.storage_lock(data):
        item = next((i for i in overview(data)['items'] if i['id'] == payload.get('id')), None)
        if not item or item['fingerprint'] != payload.get('fingerprint'):
            raise core.MnemosError('This finding changed or was resolved. Refresh the health page.', 409)
        state = _state(data)
        if days:
            state[item['id']] = {'fingerprint': item['fingerprint'], 'until': (datetime.now(timezone.utc) + timedelta(days=days)).isoformat()}
        else:
            state.pop(item['id'], None)
        active = {i['id'] for i in overview(data)['items']}
        state = {k: v for k, v in state.items() if k in active}
        core.atomic_write(core.safe_path(Path(data), 'health-state/state.json'), json.dumps(state))
        return {'snoozed': bool(days)}
