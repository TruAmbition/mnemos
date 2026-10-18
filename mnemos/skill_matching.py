"""Explainable local metadata matching; no inference, execution, or installation."""
import re
from . import core, skill_builder, skill_inventory

STOP = set('a an and are as at be been by can documented documentation for from has have in into is it its local mnemos of on or our procedure repeat reusable skill skills step steps task the their this to use using when with workflow your asked follow'.split())


def tokens(text):
    return {word for word in re.findall(r'[a-z0-9]+', text.lower())
            if len(word) > 2 and word not in STOP and not re.fullmatch(r'[a-f0-9]{6,}', word)}


def rank(candidate, existing):
    wanted = tokens(candidate['title']+' '+candidate['name']+' '+candidate['description'])
    matches = []
    for item in existing:
        shared = wanted & tokens(item['name']+' '+item['description'])
        exact = candidate['name'].casefold() == item['name'].casefold()
        same_source = item.get('candidate_id') == candidate['id']
        coverage = len(shared)/max(1, len(wanted))
        if not (exact or same_source or (len(shared) >= 2 and coverage >= .25)):
            continue
        unchanged = same_source and item.get('freshness') == 'current'
        reuse = unchanged or (exact and item.get('freshness', 'current') == 'current')
        reason = ('Built from this suggestion; its sources are unchanged.' if unchanged else
                  'Built from this suggestion, but its sources changed or are unavailable.' if same_source else
                  'The skill name matches exactly; compare its scope and environment.' if exact else
                  'Shared terms: '+', '.join(sorted(shared)[:8])+'. Compare the actual instructions before deciding.')
        matches.append({**item, 'recommendation': 'reuse' if reuse else 'extend', 'reason': reason,
                        '_score': (3 if same_source else 2 if exact else 1, coverage)})
    matches.sort(key=lambda m: (m['_score'], m['name']), reverse=True)
    total = len(matches)
    for item in matches: item.pop('_score')
    return {'matches': matches[:8], 'total': total,
            'recommendation': 'reuse' if any(m['recommendation']=='reuse' for m in matches) else 'extend' if matches else 'create'}


def check(data, payload):
    if not isinstance(payload, dict): raise core.MnemosError('Choose a skill suggestion first.')
    candidate = next((c for c in skill_builder.candidates(data, include_examples=True)['candidates']
                      if c['id'] == payload.get('candidate_id')), None)
    if not candidate or candidate['revision'] != payload.get('revision'):
        raise core.MnemosError('The suggestion changed. Refresh it before checking existing skills.', 409)
    candidate = dict(candidate)
    for field, limit in [('name', 63), ('description', 200)]:
        value = payload.get(field, candidate[field])
        if not isinstance(value, str) or not value.strip() or len(value) > limit:
            raise core.MnemosError('Enter a valid skill '+field+'.')
        candidate[field] = value
    inventory = skill_inventory.inventory(data)
    existing = [{**s, 'kind': 'local'} for s in inventory['skills']]
    existing += [{**s, 'kind': 'built', 'location': 'Saved Mnemos package',
                  'status': {'current':'Sources unchanged', 'changed':'Sources changed — review before reuse',
                             'unavailable':'Source unavailable — review before reuse'}[s['freshness']]}
                 for s in skill_builder.list_builds(data)]
    return {**rank(candidate, existing), 'scanned': len(existing), 'warnings': inventory['warnings'],
            'notice': 'Based on names, descriptions, and saved-build provenance, not AI analysis of instructions. '
                      'Possible matches are not proof of equivalence or readiness. '+inventory['notice']}
