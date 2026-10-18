"""Read-only knowledge graph. Every edge comes from a recorded relationship."""
from pathlib import PurePosixPath, Path
import re
from urllib.parse import unquote
from . import core, knowledge_projects as kp, privacy


def assemble(documents, projects=(), repositories=(), workflows=(), skills=()):
    nodes = {}; edges = {}; indexed = {d['id']: d for d in documents}
    aliases = {}
    for d in documents:
        for alias in {d['id'], d.get('path') or d['id'], str(PurePosixPath(d.get('path') or d['id']).with_suffix('')), PurePosixPath(d.get('path') or d['id']).stem, d['title']}:
            if alias: aliases.setdefault(alias.casefold(), set()).add(d['id'])
    def node(identifier, label, kind, **extra):
        nodes[identifier] = dict(id=identifier, label=label, kind=kind, **extra)
    def edge(source, target, relation):
        if source != target and source in nodes and target in nodes:
            edges[(source, target, relation)] = dict(source=source, target=target, relation=relation)
    for p in projects:
        node('project:' + p['id'], p['name'], 'project', project_ids=[p['id']], summary=p.get('purpose', ''), project_id=p['id'])
    for r in repositories:
        membership = [p['id'] for p in projects if r['id'] in p.get('repository_ids', [])]
        node('repo:' + r['id'], r['name'], 'repository', project_ids=membership, summary='Registered source repository. This graph does not read or change its checkout.')
    for d in documents:
        kind = {'knowledge-item':'knowledge', 'micro-task':'microtask'}.get(d.get('type'), d.get('type', 'knowledge'))
        node('note:' + d['id'], d['title'], kind, document_id=d['id'], project_ids=d.get('project_ids', []),
             summary=d.get('summary', ''), status=d.get('status', 'draft'), example=bool(d.get('example')))
    for w in workflows:
        sources = [s.get('document_id') for s in w.get('steps', [])]
        membership = sorted({p for identifier in sources for p in indexed.get(identifier, {}).get('project_ids', [])})
        node('workflow:' + w['id'], w.get('title', w.get('name', w['id'])), 'workflow', project_ids=membership,
             summary=w.get('description', ''), workflow_id=w['id'])
    for s in skills:
        membership = sorted({p for identifier in s.get('source_ids', []) for p in indexed.get(identifier, {}).get('project_ids', [])})
        node('package:' + s['id'], s['name'], 'skill-package', project_ids=membership,
             summary=s.get('description', ''), target=s.get('target', ''), built_id=s['id'])
    for p in projects:
        for identifier in p.get('repository_ids', []): edge('project:' + p['id'], 'repo:' + identifier, 'contains repository')
        for r in p.get('relationships', []): edge('repo:' + r['from'], 'repo:' + r['to'], r['kind'])
    for d in documents:
        source = 'note:' + d['id']
        for identifier in d.get('project_ids', []): edge('project:' + identifier, source, 'contains documentation')
        for identifier in kp.document_repositories(d, repositories): edge('repo:' + identifier, source, 'documented by')
        for identifier in d.get('related_ids', []): edge(source, 'note:' + identifier, 'related note')
        for reference in d.get('sources', []):
            if reference.startswith('mnemos:'): edge(source, 'note:' + reference[7:].split('@', 1)[0], 'uses source')
        # Wiki aliases/headings and ordinary relative Markdown note links resolve only
        # to a visible, unambiguous existing note; no phantom/private nodes are created.
        body = re.sub(r'(?ms)^\s*(```|~~~).*?^\s*\1[^\n]*$', '', d.get('body', ''))
        body = re.sub(r'(?s)<!--.*?-->|`[^`]*`', '', body)
        links = re.findall(r'\[\[([^\]\n]+)\]\]', body)
        links += re.findall(r'(?<!!)\[[^\]\n]*\]\(([^)\s]+)\)', body)
        for reference in links:
            reference = unquote(reference.split('|', 1)[0].split('#', 1)[0])
            if not reference or '://' in reference: continue
            matches = aliases.get(reference.casefold(), set())
            if len(matches) != 1:
                parent = PurePosixPath(d.get('path') or d['id']).parent
                parts = []
                for part in (parent / reference).parts:
                    if part == '..':
                        if parts: parts.pop()
                    elif part != '.': parts.append(part)
                matches = aliases.get('/'.join(parts).casefold(), set())
            if len(matches) == 1: edge(source, 'note:' + next(iter(matches)), 'links to')
    for w in workflows:
        for step in w.get('steps', []): edge('workflow:' + w['id'], 'note:' + str(step.get('document_id', '')), 'uses step')
    for s in skills:
        for identifier in s.get('source_ids', []): edge('package:' + s['id'], 'note:' + identifier, 'built from')
    neighbors = {n: set() for n in nodes}
    for e in edges.values():
        neighbors[e['source']].add(e['target']); neighbors[e['target']].add(e['source'])
    for identifier, item in nodes.items(): item['connections'] = len(neighbors[identifier])
    return {'nodes': list(nodes.values()), 'edges': list(edges.values()),
            'notice': 'Only recorded links and memberships are shown. Layout and orb size are visual aids, not AI confidence or importance scores.'}


def build(data, role='owner', local=False):
    with core.storage_lock(data):
        docs = core.list_documents(data, role)
        # An API token, even owner, must never receive local checkout or saved-build metadata.
        local = local and role == 'owner' and privacy.AUDIENCE.get() == 'local'
        projects = kp.entries(data) if local else kp.catalog(data, role, docs)
        repos = core.load_config(data).get('projects', []) if local else []
        workflows = core.list_workflows(data, role) if role != 'anonymous' else []
        skills = []
        if local:
            from .skill_builder import read
            folder = core.safe_path(Path(data), 'skill-builds')
            for path in sorted(folder.glob('skill-*.json'))[:500] if folder.exists() else []:
                try:
                    built = read(data, path.stem, for_export=False)
                    skills.append({k: built.get(k, '') for k in ('id', 'name', 'description', 'target')} |
                                  {'source_ids': [d['id'] for d in built.get('candidate', {}).get('sources', [])]})
                except (core.MnemosError, KeyError, TypeError): continue
        result = assemble(docs, projects, repos, workflows, skills)
        result['scope'] = 'local workspace' if local else 'documentation visible to this session'
        return result
