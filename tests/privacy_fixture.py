"""Explicit sharing consent for synthetic fixtures in pre-existing feature tests."""
from mnemos import core, privacy, knowledge_projects


def allow_fixture(data, ids=None, mode='team', approve=True):
    for project in knowledge_projects.overview(data)['knowledge_projects']:
        if project.get('privacy') != mode:
            knowledge_projects.save(data, {**project, 'privacy': mode})
    docs = core.list_documents(data)
    for doc in docs:
        if not doc['project_ids'] and (ids is None or doc['id'] in ids):
            doc = core.get_document(data, doc['id'])
            privacy.update(data, {'id': doc['id'], 'fingerprint': doc['privacy']['fingerprint'], 'operation': 'policy', 'mode': mode})
    if approve:
        for doc in core.list_documents(data):
            if ids is None or doc['id'] in ids:
                privacy.update(data, {'id': doc['id'], 'fingerprint': doc['privacy']['fingerprint'], 'operation': 'approve', 'reviewed': True})
