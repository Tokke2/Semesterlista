"""Build ONE portable release ZIP with native Windows/macOS/Linux entry points.

Run on macOS: python tools/build_release.py --output /path/release.zip
No Python installer or third-party runtime is bundled. Requires only stdlib and
macOS built-ins to compile the terminal-free applet (no Python needed at launch).
"""
import argparse
import json
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from core.platform_launch import desktop_exec  # noqa: E402

FORBIDDEN = {'installera senaste python.bat', 'starta semesterlista.cmd'}
MAC_APP = 'Starta Semesterlista macOS.app'
LINUX_DESKTOP = 'Starta Semesterlista Linux.desktop'

# Read CRLF payload as normalized shell input; never execute it by shebang.
SHELL_CODE = 'exec /bin/sh -c "$(/usr/bin/tr -d \'\\r\' < "$1/tools/start_posix.sh")" starter "$1"'


def linux_launcher():
    code = ('root=$(CDPATH= cd -- "$(dirname -- "$1")" && pwd) || exit 1; '
            'exec /bin/sh -c ' + "'" + SHELL_CODE.replace("'", "'\\''") + "'" + ' starter "$root"')
    return ('[Desktop Entry]\nType=Application\nName=Starta Semesterlista\n'
            'Comment=Starta appen; Python-installation erbjuds bara om Python saknas helt\n'
            'Exec=' + desktop_exec(['/bin/sh', '-c', code, 'starter']) + ' %k\n'
            'Icon=office-calendar\nTerminal=false\nCategories=Office;Calendar;\n')


def macos_source():
    return '\n'.join([
        'set appPath to POSIX path of (path to me)',
        'set appRoot to do shell script "/usr/bin/dirname " & quoted form of (text 1 thru -2 of appPath)',
        'set shellCode to ' + json.dumps(SHELL_CODE),
        'do shell script "nohup /bin/sh -c " & quoted form of shellCode & " starter " & quoted form of appRoot & " >/dev/null 2>&1 &"',
    ])


def compile_macos(root):
    target = root / MAC_APP
    subprocess.run(['/usr/bin/osacompile', '-o', str(target), '-e', macos_source()], check=True, timeout=60)
    with tempfile.TemporaryDirectory() as temporary:
        iconset = Path(temporary) / 'AppIcon.iconset'
        iconset.mkdir()
        for size in (16, 32, 128, 256, 512):
            for scale in (1, 2):
                suffix = '@2x' if scale == 2 else ''
                output = iconset / f'icon_{size}x{size}{suffix}.png'
                subprocess.run(['/usr/bin/sips', '-z', str(size*scale), str(size*scale),
                                str(root / 'assets/ikon/appikon-256.png'), '--out', str(output)],
                               capture_output=True, check=True, timeout=30)
        subprocess.run(['/usr/bin/iconutil', '-c', 'icns', str(iconset), '-o',
                        str(target / 'Contents/Resources/applet.icns')], check=True, timeout=30)
    plist = target / 'Contents/Info.plist'
    info = plistlib.loads(plist.read_bytes())
    info.update(CFBundleIdentifier='se.semesterlista.bootstrap', CFBundleName='Semesterlista')
    plist.write_bytes(plistlib.dumps(info))
    # Valid local signature, NOT Apple notarization or Developer ID distribution.
    subprocess.run(['/usr/bin/codesign', '--force', '--deep', '--sign', '-', str(target)],
                   check=True, capture_output=True, timeout=30)
    return target


def verify_archive(path):
    with zipfile.ZipFile(path) as archive:
        names = archive.namelist()
        required = ['Starta Semesterlista.vbs', LINUX_DESKTOP, MAC_APP + '/Contents/Info.plist',
                    MAC_APP + '/Contents/MacOS/applet', 'main.pyw', 'tools/start_posix.sh',
                    'assets/brand/logotyp-tryck.svg', 'assets/brand/logotyp-svart.svg',
                    'assets/brand/FONT-LICENSE.txt']
        for name in required:
            if 'Semesterlista/' + name not in names:
                raise ValueError('Missing release file: ' + name)
        for name in names:
            if Path(name).name.casefold() in FORBIDDEN:
                raise ValueError('Forbidden installer/extra Windows launcher: ' + name)
        if archive.testzip() is not None:
            raise ValueError('Damaged ZIP')


def build(output, source=ROOT):
    if sys.platform != 'darwin':
        raise RuntimeError('Build on macOS so the release includes a real native .app')
    output = Path(output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary) / 'Semesterlista'
        stage.mkdir()
        source_zip = Path(temporary) / 'source.zip'
        subprocess.run(['git', 'archive', '--format=zip', 'HEAD', '-o', str(source_zip)],
                       cwd=source, check=True)
        with zipfile.ZipFile(source_zip) as archive:
            archive.extractall(stage)
        for path in list(stage.rglob('*')):
            if path.is_file() and path.name.casefold() in FORBIDDEN:
                path.unlink()
        shutil.rmtree(stage / '.github', ignore_errors=True)
        (stage / LINUX_DESKTOP).write_text(linux_launcher(), encoding='utf-8', newline='\r\n')
        (stage / LINUX_DESKTOP).chmod(0o755)
        compile_macos(stage)
        with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
            for path in sorted(stage.rglob('*')):
                if path.is_file():
                    archive.write(path, path.relative_to(stage.parent).as_posix())
    verify_archive(output)
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    print(build(args.output))


if __name__ == '__main__':
    main()
