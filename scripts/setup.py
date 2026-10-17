#!/usr/bin/env python3
"""Create an isolated Keystone vault and install Obsidian when needed."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from keystone.core import initialize, load_config, update_settings


def detect_obsidian(data):
    if platform.system() == 'Darwin':
        for path in [Path('/Applications/Obsidian.app'), Path.home() / 'Applications/Obsidian.app']:
            if path.is_dir():
                return str(path)
    if platform.system() == 'Windows':
        for base in [os.environ.get('LOCALAPPDATA', ''), os.environ.get('PROGRAMFILES', '')]:
            if base:
                for relative in ['Obsidian/Obsidian.exe', 'Programs/Obsidian/Obsidian.exe']:
                    path = Path(base) / relative
                    if path.exists():
                        return str(path)
    executable = shutil.which('obsidian')
    if executable:
        return executable
    appimage = data / 'tools' / 'Obsidian.AppImage'
    if appimage.exists():
        return str(appimage)
    if platform.system() == 'Linux' and shutil.which('flatpak'):
        result = subprocess.run(['flatpak', 'info', 'md.obsidian.Obsidian'], capture_output=True)
        if result.returncode == 0:
            return 'flatpak:md.obsidian.Obsidian'
    return None


def download_official_asset(system, target):
    request = Request('https://api.github.com/repos/obsidianmd/obsidian-releases/releases/latest', headers={'User-Agent': 'Keystone-Setup/0.1'})
    with urlopen(request, timeout=30) as response:
        release = json.load(response)
    architecture = platform.machine().lower()
    def matches(asset):
        name = asset['name'].lower()
        if system == 'Darwin':
            return name.endswith('.dmg')
        if system == 'Windows':
            return name.endswith('.exe') and 'arm' not in name
        if architecture in {'arm64', 'aarch64'}:
            return name.endswith('.appimage') and 'arm64' in name
        if architecture in {'x86_64', 'amd64'}:
            return name.endswith('.appimage') and 'arm' not in name
        return False
    asset = next((a for a in release['assets'] if matches(a)), None)
    if asset is None:
        raise RuntimeError('No matching official installer. Download Obsidian from https://obsidian.md/download.')
    url = asset['browser_download_url']
    if not url.startswith('https://github.com/obsidianmd/obsidian-releases/releases/download/'):
        raise RuntimeError('Unexpected installer download host.')
    target.parent.mkdir(parents=True, exist_ok=True)
    with urlopen(Request(url, headers={'User-Agent': 'Keystone-Setup/0.1'}), timeout=60) as response, target.open('wb') as stream:
        shutil.copyfileobj(response, stream)
    digest = asset.get('digest')
    if digest and digest.startswith('sha256:'):
        actual = hashlib.sha256(target.read_bytes()).hexdigest()
        if actual != digest.split(':', 1)[1]:
            target.unlink()
            raise RuntimeError('Official installer checksum mismatch.')
    return target


def install_obsidian(data):
    found = detect_obsidian(data)
    if found:
        return found
    system = platform.system()
    print('Obsidian was not found. Installing it without modifying other vaults…')
    if system == 'Darwin' and shutil.which('brew'):
        subprocess.run(['brew', 'install', '--cask', 'obsidian'], check=True)
    elif system == 'Windows' and shutil.which('winget'):
        subprocess.run(['winget', 'install', '--id', 'Obsidian.Obsidian', '--exact', '--source', 'winget',
                        '--accept-package-agreements', '--accept-source-agreements'], check=True)
    elif system == 'Linux' and shutil.which('flatpak'):
        subprocess.run(['flatpak', 'remote-add', '--user', '--if-not-exists', 'flathub', 'https://flathub.org/repo/flathub.flatpakrepo'], check=True)
        subprocess.run(['flatpak', 'install', '--user', '-y', 'flathub', 'md.obsidian.Obsidian'], check=True)
    elif system == 'Linux':
        target = download_official_asset(system, data / 'tools' / 'Obsidian.AppImage')
        target.chmod(0o755)
    elif system == 'Darwin':
        with tempfile.TemporaryDirectory(prefix='keystone-obsidian-') as temporary:
            folder = Path(temporary)
            installer = download_official_asset(system, folder / 'Obsidian.dmg')
            mount = folder / 'mounted'
            subprocess.run(['hdiutil', 'attach', str(installer), '-nobrowse', '-mountpoint', str(mount)], check=True)
            try:
                app = mount / 'Obsidian.app'
                subprocess.run(['codesign', '--verify', '--deep', '--strict', str(app)], check=True)
                destination = Path.home() / 'Applications' / 'Obsidian.app'
                if destination.exists():
                    raise RuntimeError('Obsidian appeared during setup; refusing to overwrite it.')
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copytree(app, destination, symlinks=True)
            finally:
                subprocess.run(['hdiutil', 'detach', str(mount)], check=True)
    elif system == 'Windows':
        with tempfile.TemporaryDirectory(prefix='keystone-obsidian-') as temporary:
            installer = download_official_asset(system, Path(temporary) / 'Obsidian.exe')
            subprocess.run([str(installer), '/S'], check=True)
    else:
        raise RuntimeError('Unsupported desktop OS. Use --skip-obsidian on a server, or install from https://obsidian.md/download.')
    found = detect_obsidian(data)
    if not found:
        raise RuntimeError('Installation ran but Obsidian was not detected. Complete the installer and run setup again.')
    return found


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--data', default=str(ROOT / 'data'))
    parser.add_argument('--author')
    parser.add_argument('--backup', choices=['local', 'rclone'])
    parser.add_argument('--destination')
    parser.add_argument('--remote')
    parser.add_argument('--skip-obsidian', action='store_true', help='For cloud/headless environments; leave desktop install unchanged.')
    parser.add_argument('--yes', action='store_true', help='Use defaults for unspecified setup choices.')
    args = parser.parse_args()
    if sys.version_info < (3, 11):
        parser.exit(1, 'Python 3.11 or newer is required.\n')
    data = Path(args.data).expanduser().absolute()
    if data.is_symlink():
        parser.exit(1, 'Choose a dedicated data directory, not a symlink.\n')
    data = data.resolve()
    existing = (data / 'config.json').exists()
    if existing:
        config = load_config(data)
        author = config['owner']
    else:
        author = args.author or ('Local engineer' if args.yes else input('Your author name [Local engineer]: ').strip() or 'Local engineer')
        config = initialize(data, author)
    selected = args.backup
    if selected is None:
        selected = config['backup']['provider'] if args.yes or existing else ('rclone' if input('Backup storage: local or cloud [local]: ').strip().lower() == 'cloud' else 'local')
    destination = Path(args.destination).expanduser().resolve() if args.destination else Path(config['backup']['destination'])
    remote = args.remote if args.remote is not None else config['backup'].get('remote', '')
    if selected == 'rclone' and not remote and not args.yes:
        remote = input('Configured rclone remote (e.g. encrypted:keystone): ').strip()
    if selected == 'rclone' and (not remote or ':' not in remote):
        parser.exit(1, 'Cloud backup needs --remote configured-name:path. Configure credentials with rclone config.\n')
    vault = data / 'vault'
    if destination.resolve() == vault or vault in destination.resolve().parents:
        parser.exit(1, 'Backup destination must be outside the vault.\n')
    update_settings(data, {'backup': {'provider': selected, 'destination': str(destination), 'remote': remote}})
    obsidian = 'Skipped for a headless environment' if args.skip_obsidian else install_obsidian(data)
    print(f'\nKeystone is ready for {author}.')
    print(f'Obsidian: {obsidian}')
    print(f'Dedicated vault: {vault}')
    print('In Obsidian, choose Open folder as vault and select that folder once.')
    print(f'Backup storage: {selected}. ' + ('Configure rclone credentials before the first cloud backup.' if selected == 'rclone' else 'Snapshots are created on demand.'))
    print(f'Start the portal: {sys.executable} -m keystone serve --data "{data}"')
    print('Open http://127.0.0.1:4318')
    print('Reusable assistant skills are in skills/. Copy the desired skills into your agent workspace.')
    return 0


if __name__ == '__main__':
    try:
        raise SystemExit(main())
    except (RuntimeError, ValueError, OSError, subprocess.SubprocessError) as error:
        print(f'Setup could not finish: {error}', file=sys.stderr)
        raise SystemExit(1)
