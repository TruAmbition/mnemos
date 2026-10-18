"""Private launcher credentials; never print them or put them in URL queries."""
import os
from pathlib import Path
import secrets
from . import core


def key_path(base, port):
    return core.safe_path(Path(base).parent, f'.mnemos-access/{Path(base).name}-{port}.key')


def create(base, port):
    path = key_path(base, port)
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if os.name != 'nt':
        os.chmod(path.parent, 0o700)
    key = secrets.token_urlsafe(48)
    core.atomic_write(path, key)
    if os.name != 'nt':
        os.chmod(path, 0o600)
    return key


def read(base, port):
    path = key_path(base, port)
    try:
        if path.stat().st_size > 128:
            return ''
        return path.read_text().strip()
    except OSError:
        return ''


def browser_url(url, key, route=''):
    # The fragment is removed before any page requests; it is never sent to HTTP.
    return url.split('#', 1)[0] + '#local-access=' + key + '&route=' + route.lstrip('#')
