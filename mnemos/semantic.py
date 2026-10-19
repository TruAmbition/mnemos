"""Optional local embeddings. No cloud URLs, proxies, redirects, or model downloads."""
from __future__ import annotations
import http.client
import json
import math
from pathlib import Path
from . import core, privacy

MODELS = ('embeddinggemma', 'nomic-embed-text', 'all-minilm')
CACHE = 'search-index.json'


def _http(method, path, payload=None):
    connection = http.client.HTTPConnection('127.0.0.1', 11434, timeout=60)
    try:
        connection.request(method, path, json.dumps(payload) if payload else None,
                           {'Content-Type': 'application/json'})
        response = connection.getresponse()
        raw = response.read(20_000_001)
        if response.status != 200 or len(raw) > 20_000_000:
            raise ValueError()
        value = json.loads(raw)
        if not isinstance(value, dict):
            raise ValueError()
        return value
    except (OSError, ValueError, http.client.HTTPException) as exc:
        raise core.MnemosError('Local search model unavailable. Start Ollama and install the selected embedding model, or use keyword search.', 503) from exc
    finally:
        connection.close()


def settings(data):
    value = core.load_config(data).get('semantic_search', {})
    return {'enabled': value.get('enabled') is True, 'model': value.get('model', MODELS[0])}


def configure(data, payload):
    if type(payload.get('enabled')) is not bool or payload.get('model') not in MODELS:
        raise core.MnemosError('Choose on/off and a supported local embedding model.')
    with core.storage_lock(data):
        config = core.load_config(data)
        config['semantic_search'] = {k: payload[k] for k in ('enabled', 'model')}
        core.save_config(data, config)
        # Disabling also removes the derived private index.
        core.safe_path(Path(data), CACHE).unlink(missing_ok=True)
    return status(data)


def _cache(data):
    path = core.safe_path(Path(data), CACHE)
    try:
        if path.stat().st_size > 100_000_000:
            return {}
        value = json.loads(path.read_text(encoding='utf-8'))
        return value if isinstance(value, dict) and isinstance(value.get('notes'), dict) else {}
    except (FileNotFoundError, ValueError):
        return {}


def status(data):
    config = settings(data)
    cached = _cache(data)
    docs = [d for d in core.list_documents(data) if d['status'] != 'archived']
    ready = sum(cached.get('model') == config['model'] and cached.get('notes', {}).get(d['id'], {}).get('revision') == d['revision'] for d in docs)
    return {**config, 'models': list(MODELS), 'indexed': ready, 'total': len(docs),
            'updated': cached.get('updated'), 'endpoint': 'http://127.0.0.1:11434',
            'notice': 'Uses your local Ollama service. No model is downloaded automatically. The private index is rebuildable and excluded from backups.'}


def _model(config):
    if not config['enabled'] or config['model'] not in MODELS:
        raise core.MnemosError('Meaning search is off. Enable it in Search settings, or choose keyword search.')
    models = _http('GET', '/api/tags').get('models', [])
    model = next((m for m in models if m.get('name') in {config['model'], config['model'] + ':latest'}), None)
    if not model or not model.get('digest') or model.get('remote_host') or model.get('remote_model'):
        raise core.MnemosError('Install the selected local embedding model in Ollama first. Cloud models are not supported.', 503)
    return model['digest']


def _vector(value):
    if (not isinstance(value, list) or not 1 <= len(value) <= 8192
            or any(type(n) not in (int, float) or not math.isfinite(n) for n in value)):
        raise core.MnemosError('The local model returned an invalid embedding.', 503)
    norm = math.sqrt(sum(n*n for n in value))
    if not math.isfinite(norm) or norm == 0:
        raise core.MnemosError('The local model returned an empty embedding.', 503)
    return [n/norm for n in value]


def _embed(model, texts, query=False):
    if model == 'nomic-embed-text':
        texts = [('search_query: ' if query else 'search_document: ') + t for t in texts]
    values = _http('POST', '/api/embed', {'model': model, 'input': texts, 'truncate': False}).get('embeddings')
    if not isinstance(values, list) or len(values) != len(texts):
        raise core.MnemosError('The local model returned incomplete embeddings.', 503)
    vectors = [_vector(v) for v in values]
    if len({len(v) for v in vectors}) != 1:
        raise core.MnemosError('The local model returned inconsistent embeddings.', 503)
    return vectors


def _index(data, documents, config, digest):
    cached = _cache(data)
    if cached.get('model') != config['model'] or cached.get('digest') != digest:
        cached = {'model': config['model'], 'digest': digest, 'notes': {}}
    notes = cached.setdefault('notes', {})
    # Retain other project scopes, but discard deleted/archived notes.
    current = {d['id']:d['revision'] for d in core.list_documents(data) if d['status'] != 'archived'}
    notes = {identifier: value for identifier, value in notes.items() if current.get(identifier) == value.get('revision')}
    pending = [(d, (d['title']+'\n'+d['summary']+'\n'+d['body'])) for d in documents
               if notes.get(d['id'], {}).get('revision') != d['revision']]
    if sum(max(1, math.ceil(len(t)/2200)) for _, t in pending) > 5000:
        raise core.MnemosError('Index refresh exceeds 5,000 passages. Index a smaller project scope first.')
    for doc, text in pending:
        chunks = [text[i:i+2400] for i in range(0, len(text), 2200)] or [doc['title']]
        vectors = []
        for i in range(0, len(chunks), 16):
            vectors += _embed(config['model'], chunks[i:i+16])
        notes[doc['id']] = {'revision': doc['revision'], 'vectors': vectors}
    cached.update(notes=notes, updated=core.now())
    core.atomic_write(core.safe_path(Path(data), CACHE), json.dumps(cached))
    return notes


def rebuild(data):
    with core.storage_lock(data):
        config = settings(data)
        digest = _model(config)
        _index(data, [d for d in core.list_documents(data) if d['status'] != 'archived'], config, digest)
        return status(data)


def search(data, query, project_id='', kind='all'):
    if privacy.AUDIENCE.get() != 'local':
        raise core.MnemosError('Meaning search is available to the local owner only.', 403)
    if not isinstance(query, str) or not 1 <= len(query.strip()) <= 1000:
        raise core.MnemosError('Enter a search between 1 and 1,000 characters.')
    from .knowledge_projects import scope
    from .recall import current_project_context, _terms
    with core.storage_lock(data):
        config = settings(data)
        digest = _model(config)
        documents = [d for d in current_project_context(data, scope(core.list_documents(data), project_id))
                     if d['status'] != 'archived' and (kind == 'all' or d['type'] == kind)]
        notes = _index(data, documents, config, digest)
        q = _embed(config['model'], [query], query=True)[0]
        result = []
        for doc in documents:
            vectors = notes[doc['id']]['vectors']
            if any(len(v) != len(q) for v in vectors):
                raise core.MnemosError('The model dimensions changed. Save search settings and rebuild the index.', 409)
            scores = [sum(a*b for a,b in zip(q, _vector(v))) for v in vectors]
            passage = max(range(len(scores)), key=lambda i:scores[i])
            similarity = scores[passage]
            title = (doc['title']+' '+doc['summary']+' '+' '.join(doc['tags'])).casefold()
            lexical = sum(t in title for t in _terms(query))
            if similarity >= .25 or lexical:
                result.append({**doc, 'search_score': round(similarity + min(.15, lexical*.03), 4),
                               'similarity': round(similarity, 4),
                               'semantic_excerpt': (doc['title']+'\n'+doc['summary']+'\n'+doc['body'])[passage*2200:passage*2200+2400]})
        result.sort(key=lambda d: (-d['search_score'], d['id']))
        return {'documents': result[:50], 'method': 'local-embeddings-and-keywords', 'model': config['model'],
                'notice': 'Similarity ranks possible matches; it does not verify that a note answers your question.'}
