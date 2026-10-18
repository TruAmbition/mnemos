"""Portable reader builds; exporting creates an unencrypted copy of verified notes."""
from pathlib import Path
import json
import shutil
from .backup import snapshot_bytes
from . import __version__


def vault_archive(data_path):
    from .core import load_config, storage_lock, vault_path
    with storage_lock(data_path):
        load_config(data_path)
        from .privacy import full_export
        full_export(data_path)
        return snapshot_bytes(vault_path(data_path))[0]


def build_reader(data_path, output):
    from .core import list_documents, list_workflows, storage_lock, vault_path
    output = Path(output).expanduser().absolute()
    vault = vault_path(data_path).resolve()
    if output.is_symlink() or output.resolve() == vault or vault in output.resolve().parents:
        raise ValueError('Reader export must be outside the vault and cannot be a symlink.')
    if output.exists() and any(output.iterdir()):
        raise ValueError('Choose an empty output directory for the reader export.')
    with storage_lock(data_path):
        documents = list_documents(data_path, role='reader')
        workflows = list_workflows(data_path, role='reader')
    from .knowledge_projects import catalog
    payload = {'knowledge_projects': catalog(data_path, 'reader', documents), 'app': {'name': 'Mnemos', 'version': __version__}, 'session': {'role': 'reader', 'author': 'Reader'},
               'documents': documents, 'workflows': workflows,
               'settings': {}, 'static': True, 'sample': all(d.get('example') for d in documents)}
    from .graph import assemble
    payload['graph'] = assemble(documents, payload['knowledge_projects'], workflows=workflows)
    output.mkdir(parents=True, exist_ok=True)
    web = Path(__file__).resolve().parents[1] / 'web'
    for source in web.iterdir():
        if source.is_symlink():
            raise ValueError('Reader assets cannot be symlinks.')
        if source.is_file() and source.name not in {'data.json', 'config.js'}:
            shutil.copy2(source, output / source.name)
    (output / 'config.js').write_text('window.MNEMOS_STATIC = true;\n')
    (output / 'data.json').write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    return {'path': str(output), 'documents': len(documents), 'private': False,
            'notice': 'Static files contain readable documentation. Host behind access control; do not publish private notes on public Pages.'}
