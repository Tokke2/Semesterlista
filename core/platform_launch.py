"""Qt-free launch commands and freedesktop launcher serialization."""
from pathlib import Path
import sys
from core.roster import app_root


def launch_arguments(root=None):
    if getattr(sys, 'frozen', False):
        return [sys.executable]
    executable = getattr(sys, '_base_executable', None) or sys.executable
    return [executable, str(Path(root or app_root()) / 'tools' / 'runtime_check.py')]


def desktop_value(value):
    value = str(value)
    if any(char in value for char in '\n\r\0'):
        raise ValueError('Launcher paths cannot contain line breaks or NUL')
    return value.replace('\\', '\\\\')


def desktop_exec(arguments):
    # Exec quoting is not shell quoting: escape the desktop string layer too.
    def quote(argument):
        desktop_value(argument)  # validate before escaping
        text = str(argument).replace('%', '%%')
        for char in ('\\', '"', '`', '$'):
            text = text.replace(char, '\\' + char)
        return '"' + text.replace('\\', '\\\\') + '"'
    return ' '.join(quote(arg) for arg in arguments)


def desktop_entry(root=None, name='Semesterlista'):
    root = Path(root or app_root()).resolve()
    return '\n'.join([
        '[Desktop Entry]', 'Type=Application', f'Name={desktop_value(name)}',
        f'Exec={desktop_exec(launch_arguments(root))}',
        f'Path={desktop_value(root)}',
        f'Icon={desktop_value(root / "assets" / "ikon" / "appikon-256.png")}',
        'Terminal=false', 'StartupNotify=false', 'Categories=Office;Calendar;', '',
    ])
