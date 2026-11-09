"""Prefer a working installed 3.15, then 3.14, then another supported Python.

Only local probes: never install an interpreter, packages or a virtual environment.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

PROBE = """import json, sys
ready = False
try:
    from PySide6 import QtWidgets
    import reportlab.pdfgen.canvas
    ready = True
except Exception:
    pass
print(json.dumps(dict(executable=getattr(sys, '_base_executable', sys.executable),
                      major=sys.version_info[0], minor=sys.version_info[1], ready=ready)))
"""


def preference(candidate):
    minor = candidate['minor']
    return (300 if minor == 15 else 200 if minor == 14 else 100, minor)


def select_candidate(candidates):
    supported = [item for item in candidates if item['major'] == 3 and item['minor'] >= 10]
    ordered = sorted(supported, key=preference, reverse=True)
    healthy = next((item for item in ordered if item['ready']), None)
    if healthy:
        return healthy
    # Prefer repairing a stable fallback over an unready 3.15 installation.
    return next((item for item in ordered if item['minor'] != 15), ordered[0] if ordered else None)


def installed_candidates():
    candidates = [getattr(sys, '_base_executable', None) or sys.executable]
    names = ['python3.15', 'python3.14', 'python3', 'python']
    names += [f'python3.{minor}' for minor in range(13, 9, -1)]
    for name in names:
        found = shutil.which(name)
        if found:
            candidates.append(found)
        for folder in ('/opt/homebrew/bin', '/usr/local/bin', '/usr/bin'):
            path = Path(folder) / name
            if path.is_file() and os.access(path, os.X_OK):
                candidates.append(str(path))
    # Also find framework/Homebrew versions that are not linked into PATH.
    for pattern in ('/Library/Frameworks/Python.framework/Versions/3.*/bin/python3',
                    '/opt/homebrew/opt/python@3.*/bin/python3.*',
                    '/usr/local/opt/python@3.*/bin/python3.*'):
        import glob
        candidates.extend(p for p in glob.glob(pattern) if Path(p).is_file() and os.access(p, os.X_OK))
    return list(dict.fromkeys(os.path.realpath(path) for path in candidates))


def probe(executable):
    try:
        result = subprocess.run([executable, '-c', PROBE], capture_output=True, text=True,
                                encoding='utf-8', errors='replace', timeout=15,
                                env=dict(os.environ, PYTHONIOENCODING='utf-8'),
                                creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
        if result.returncode != 0:
            return None
        data = json.loads(result.stdout.strip().splitlines()[-1])
        if not isinstance(data['minor'], int) or not isinstance(data['major'], int):
            return None
        if not isinstance(data['ready'], bool) or not Path(data['executable']).is_absolute():
            return None
        return data
    except (OSError, subprocess.TimeoutExpired, ValueError, KeyError, IndexError, TypeError):
        return None


def select_python():
    found = []
    seen = set()
    for path in installed_candidates():
        if path in seen:
            continue
        seen.add(path)
        data = probe(path)
        if data and os.path.realpath(data['executable']) != os.path.realpath(path):
            data = probe(data['executable'])
        if data:
            found.append(data)
            seen.add(os.path.realpath(data['executable']))
    selected = select_candidate(found)
    if not selected:
        raise RuntimeError('Ingen fungerande installerad Python 3.10+ hittades. Ingen extra Python installeras.')
    return selected['executable']
