"""Bounded, read-only discovery of local SKILL.md manifests; never execute skills."""
from __future__ import annotations
import hashlib
import os
from pathlib import Path
from . import core

MAX_ENTRIES = 5000
MAX_SKILLS = 500


def roots(data):
    home=Path.home()
    result=[('Personal · agents',home/'.agents/skills'),
            ('Personal · Codex',Path(os.environ.get('CODEX_HOME',home/'.codex'))/'skills'),
            ('Personal · Claude',home/'.claude/skills'),
            ('Cached plugins · may be inactive',Path(os.environ.get('CODEX_HOME',home/'.codex'))/'plugins/cache')]
    projects=[('Mnemos checkout',core.ROOT),*[(p.get('name','Project'),Path(p['path'])) for p in core.load_config(data).get('projects',[])]]
    for label,path in projects:
        for suffix in ('.agents/skills','.claude/skills','.codex/skills'):
            result.append((label+' · '+suffix,path/suffix))
    for value in core.load_config(data).get('skill_folders',[]):result.append(('Added folder',Path(value)))
    unique={}
    for label,path in result:unique.setdefault(str(path.absolute()),(label,path.absolute()))
    return list(unique.values())


def add_folder(data,payload):
    value=payload.get('path') if isinstance(payload,dict) else None
    if not isinstance(value,str) or len(value)>4096:raise core.MnemosError('Enter an absolute skill folder path.')
    path=Path(value).expanduser()
    if not path.is_absolute() or not path.is_dir() or any(p.is_symlink() for p in [path,*path.parents]):
        raise core.MnemosError('Choose an existing absolute folder without symbolic links.')
    path=path.resolve()
    if path==Path.home() or path==Path(path.anchor):raise core.MnemosError('Choose the folder containing skills, not your home or disk root.')
    with core.storage_lock(data):
        config=core.load_config(data);folders=config.get('skill_folders',[])
        if str(path) not in folders:
            if len(folders)>=20:raise core.MnemosError('Up to 20 added skill folders are supported.')
            config['skill_folders']=[*folders,str(path)];core.atomic_write(Path(data)/'config.json',json_text(config))
    return inventory(data)


def json_text(value):
    import json
    return json.dumps(value,indent=2,ensure_ascii=False)+'\n'


def _field(text,key):
    """Read common scalar/folded manifest metadata without interpreting YAML tags."""
    meta,_=core.parse_markdown(text);value=meta.get(key,'')
    if isinstance(value,str) and value in {'>','>-','|','|-'}:
        lines=text.splitlines();start=next((i+1 for i,s in enumerate(lines) if s.startswith(key+':')),len(lines));parts=[]
        for line in lines[start:]:
            if line and not line[0].isspace():break
            parts.append(line.strip())
        return ' '.join(parts)
    return value if isinstance(value,str) else ''


def inventory(data,locations=None):
    found=[];warnings=[];seen=set();visited=0
    configured=roots(data) if locations is None else locations
    for label,root in configured:
        root=Path(root)
        if not root.exists():continue
        if any(p.is_symlink() for p in [root,*root.parents]):
            warnings.append('Skipped symbolic-link folder: '+str(root));continue
        queue=[(root,0)]
        while queue and visited<MAX_ENTRIES and len(found)<MAX_SKILLS:
            folder,depth=queue.pop(0)
            try:
                with os.scandir(folder) as entries:
                    for entry in entries:
                        visited+=1
                        if visited>MAX_ENTRIES:break
                        if entry.is_symlink():continue
                        if entry.is_dir(follow_symlinks=False) and depth<7 and entry.name not in {'.git','node_modules','__pycache__'}:
                            queue.append((Path(entry.path),depth+1))
                        elif entry.name=='SKILL.md' and entry.is_file(follow_symlinks=False):
                            path=Path(entry.path)
                            if str(path) in seen:continue
                            seen.add(str(path))
                            try:
                                with path.open('rb') as file:raw=file.read(100001)
                                if len(raw)>100000:raise ValueError('large')
                                text=raw.decode('utf-8');name=_field(text,'name');description=_field(text,'description')
                                found.append({'id':hashlib.sha256(str(path).encode()).hexdigest()[:20],
                                    'name':name[:200] or path.parent.name,'description':description[:2000],
                                    'path':str(path),'location':label,'revision':hashlib.sha256(raw).hexdigest(),
                                    'status':'Manifest found' if name and description else 'Metadata needs review'})
                            except (OSError,UnicodeError,ValueError):warnings.append('Could not read skill manifest: '+str(path))
                            if len(found)>=MAX_SKILLS:break
            except OSError:warnings.append('Could not inspect skill folder: '+str(folder))
    if visited>=MAX_ENTRIES or len(found)>=MAX_SKILLS:warnings.append('Scan limit reached; use a narrower added folder for remaining skills.')
    return {'skills':sorted(found,key=lambda s:(s['name'].casefold(),s['path'])),'warnings':warnings,
            'folders':[{'label':label,'path':str(path),'exists':Path(path).is_dir()} for label,path in configured],
            'notice':'Local files only. Found does not mean enabled in an assistant. Cached plugin versions may be inactive. Cloud-account skills are not queried.'}
