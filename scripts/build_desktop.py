#!/usr/bin/env python3
"""Build a self-contained distribution on its target OS (PyInstaller required)."""
import argparse
from pathlib import Path
import plistlib
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mnemos import __version__


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--work', required=True, type=Path)
    parser.add_argument('--dmg', action='store_true')
    args = parser.parse_args()
    output, work = args.output.resolve(), args.work.resolve()
    output.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=True)
    # Never glob the checkout: data, assistant settings, keys, and logs are excluded.
    resources = ['web', 'seed-vault', 'skills']
    staging = work / 'resources'
    staging.mkdir(exist_ok=True)
    scripts = staging / 'scripts'
    scripts.mkdir(exist_ok=True)
    from mnemos.runtime import TOOLS
    for name in TOOLS:
        shutil.copy2(ROOT / 'scripts' / (name + '.py'), scripts)
    command = [sys.executable, '-m', 'PyInstaller', '--noconfirm', '--clean', '--onedir', '--windowed' if sys.platform == 'darwin' else '--console',
               '--name', 'Mnemos', '--paths', str(ROOT), '--distpath', str(work / 'dist'),
               '--workpath', str(work / 'build'), '--specpath', str(work),
               '--collect-submodules', 'mnemos', '--collect-submodules', 'scripts',
               '--add-data', str(scripts) + ':scripts']
    icon = ROOT / 'assets/brand' / ('mnemos.icns' if sys.platform == 'darwin' else 'mnemos.ico')
    if sys.platform in {'darwin', 'win32'}:
        command += ['--icon', str(icon)]
    for resource in resources:
        command += ['--add-data', str(ROOT / resource) + ':' + resource]
    command += [str(ROOT / 'scripts/desktop.py')]
    subprocess.run(command, check=True)
    built = work / 'dist/Mnemos'
    if sys.platform == 'darwin':
        app = output / 'Mnemos.app'
        if app.exists():
            raise SystemExit('Output app already exists; use a fresh output folder.')
        shutil.copytree(work / 'dist/Mnemos.app', app, symlinks=True)
        # Keep the bundled Python runtime for CLI/MCP and service processes. The
        # visible app is native SwiftUI; its executable forwards legacy flags.
        executable = app / 'Contents/MacOS/Mnemos'
        executable.rename(executable.with_name('MnemosRuntime'))
        swift_build = ['swift', 'build', '--package-path', str(ROOT / 'desktop'),
                       '--scratch-path', str(work / 'swift'), '-c', 'release']
        subprocess.run(swift_build, check=True)
        binaries = subprocess.check_output(swift_build + ['--show-bin-path'], text=True).strip()
        shutil.copy2(Path(binaries) / 'MnemosManager', executable)
        info_path = app / 'Contents/Info.plist'
        with info_path.open('rb') as file:
            info = plistlib.load(file)
        info.update(CFBundleIdentifier='local.mnemos.desktop', CFBundleShortVersionString=__version__,
                    CFBundleVersion=__version__, LSUIElement=False,
                    LSMinimumSystemVersion='13.0',
                    NSAppTransportSecurity={'NSAllowsLocalNetworking': True})
        with info_path.open('wb') as file:
            plistlib.dump(info, file)
        subprocess.run(['codesign', '--force', '--deep', '--sign', '-', str(app)], check=True)
        subprocess.run(['ditto', '-c', '-k', '--sequesterRsrc', '--keepParent', str(app),
                        str(output / f'Mnemos-{__version__}-macOS-{platform.machine()}.zip')], check=True)
        if args.dmg:
            image = work / 'disk-image'
            image.mkdir(exist_ok=True)
            shutil.copytree(app, image / 'Mnemos.app', symlinks=True)
            (image / 'Applications').symlink_to('/Applications')
            (image / 'READ ME.txt').write_text('Drag Mnemos to Applications, then open it. No Python installation is needed.\n'
                'Use the native manager for setup, backups, projects, and service controls. Open Library for documentation.\n'
                'Closing the window keeps the local service running. Stop it from Overview.\n'
                'This developer build is ad-hoc signed, not Apple notarized. Corporate approval may be required.\n'
                'Your vault lives outside the app. Existing source checkouts are not migrated automatically.\n')
            subprocess.run(['hdiutil', 'create', '-volname', 'Mnemos', '-srcfolder', str(image),
                            '-ov', '-format', 'UDZO', str(output / f'Mnemos-{__version__}-macOS-{platform.machine()}.dmg')], check=True)
    else:
        portable = output / 'Mnemos'
        shutil.copytree(built, portable)
        if sys.platform == 'win32':
            # A separate windowless launcher preserves the runtime's stdio for MCP.
            subprocess.run([sys.executable, '-m', 'PyInstaller', '--noconfirm', '--onefile', '--windowed',
                            '--name', 'Open Mnemos', '--icon', str(icon), '--distpath', str(portable),
                            '--workpath', str(work / 'windows-launcher'), '--specpath', str(work),
                            str(ROOT / 'scripts/windows_launcher.py')], check=True)
        (portable / 'README.txt').write_text('Keep this entire folder together. Open Mnemos.exe on Windows or the Mnemos executable on Linux.\n'
            'No Python installation is required. Stop from Connections; reopen to start.\n'
            'Documentation is stored in your user application-data folder, outside this app folder.\n'
            'Unsigned developer build: follow your organization’s application approval process.\n')
        shutil.make_archive(str(output / f'Mnemos-{__version__}-{sys.platform}'), 'zip', output, 'Mnemos')
    print(f'Desktop build ready: {output}')


if __name__ == '__main__':
    main()
