"""Create a terminal-free Linux launcher or macOS application using existing Python.

Run once: python3 tools/install_launcher.py
No interpreter, packages, virtual environment or autostart are installed.
"""
from pathlib import Path
import json
import os
import platform
import plistlib
import shlex
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.platform_launch import desktop_entry, launch_arguments  # noqa: E402


def install_linux(root=ROOT):
    data_home = Path(os.environ.get('XDG_DATA_HOME', str(Path.home() / '.local' / 'share')))
    if not data_home.is_absolute():
        data_home = Path.home() / '.local' / 'share'
    target = data_home / 'applications' / 'semesterlista.desktop'
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(desktop_entry(root), encoding='utf-8', newline='\r\n')
    target.chmod(0o755)
    return target


def install_macos(root=ROOT):
    root = Path(root).resolve()
    target = root / 'Semesterlista.app'
    command = shlex.join(launch_arguments(root))
    # AppleScript gets one escaped literal; the shell gets individually quoted argv.
    shell = 'nohup ' + command + ' </dev/null >/dev/null 2>&1 &'
    source = 'do shell script ' + json.dumps(shell, ensure_ascii=False)
    # Compile in a temporary location; do not overwrite an arbitrary existing app.
    with tempfile.TemporaryDirectory(dir=root) as temporary:
        bundle = Path(temporary) / 'Semesterlista.app'
        subprocess.run(['/usr/bin/osacompile', '-o', str(bundle), '-e', source], check=True, timeout=60)
        iconset = Path(temporary) / 'AppIcon.iconset'
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                suffix = '@2x' if scale == 2 else ''
                output = iconset / f'icon_{size}x{size}{suffix}.png'
                subprocess.run(['/usr/bin/sips', '-z', str(size * scale), str(size * scale),
                                str(root / 'assets' / 'ikon' / 'appikon-256.png'),
                                '--out', str(output)], check=True, capture_output=True, timeout=30)
        resources = bundle / 'Contents' / 'Resources'
        subprocess.run(['/usr/bin/iconutil', '-c', 'icns', str(iconset), '-o',
                        str(resources / 'applet.icns')], check=True, timeout=30)
        plist_path = bundle / 'Contents' / 'Info.plist'
        info = plistlib.loads(plist_path.read_bytes())
        info.update(CFBundleIdentifier='se.semesterlista.launcher', CFBundleName='Semesterlista')
        plist_path.write_bytes(plistlib.dumps(info))
        if target.exists():
            raise FileExistsError(f'{target} finns redan. Ta bort den gamla startappen och kör igen.')
        bundle.rename(target)
    return target


def main():
    system = platform.system()
    if system == 'Linux':
        target = install_linux()
    elif system == 'Darwin':
        target = install_macos()
    else:
        print('Windows: använd Starta Semesterlista.vbs (skapar Semesterlista.lnk).')
        return 0
    print(f'Startikon skapad: {target}')
    print('Python och tillägg har inte ändrats. Flyttas appmappen behöver ikonen skapas om.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
