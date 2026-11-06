"""App-local PDF archive: type folders, atomic publication and default viewer."""
from datetime import datetime
import logging
import os
from pathlib import Path
import tempfile
from core.roster import app_root

logger = logging.getLogger(__name__)
EXPORT_TYPES = ('Kalender', 'Semesterlista', 'Fordon', 'Hyra')


def get_export_folder(kind):
    if kind not in EXPORT_TYPES:
        raise ValueError(f'Unknown PDF type: {kind}')
    folder = app_root() / 'export' / kind
    folder.mkdir(parents=True, exist_ok=True)
    return str(folder)


def _publish(temporary, target):
    """Reserve a unique name only after rendering; never replace older exports."""
    target = Path(target)
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S_%f')
    candidate = target
    counter = 0
    while True:
        try:
            descriptor = os.open(candidate, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            os.close(descriptor)
            break
        except FileExistsError:
            counter += 1
            suffix = stamp if counter == 1 else f'{stamp}_{counter}'
            candidate = target.with_name(f'{target.stem}_{suffix}{target.suffix}')
    try:
        Path(temporary).replace(candidate)
    except BaseException:
        candidate.unlink(missing_ok=True)
        raise
    return str(candidate)


def render_to_archive(target, render):
    """render(temp_path) must return True on success, False on cancellation."""
    target = Path(target)
    descriptor, temporary = tempfile.mkstemp(prefix='.export-', suffix='.pdf', dir=target.parent)
    os.close(descriptor)
    try:
        if not render(temporary):
            return None
        return _publish(temporary, target)
    finally:
        Path(temporary).unlink(missing_ok=True)


def save_document(document, elements, target, **build_options):
    def render(temporary):
        document.filename = temporary
        document.build(elements, **build_options)
        return True
    return render_to_archive(target, render)


def open_pdf(path, parent=None):
    """Open after saving, without a browser URL or a confirmation prerequisite."""
    from PySide6.QtCore import QUrl
    from PySide6.QtGui import QDesktopServices
    from PySide6.QtWidgets import QMessageBox
    from core import i18n
    try:
        if QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(path).resolve()))):
            return True
    except Exception:
        logger.exception('PDF saved, but viewer could not start: %s', path)
    logger.warning('PDF saved, but no viewer accepted it: %s', path)
    QMessageBox.warning(parent, i18n.t('pdf.open.title'), i18n.t('pdf.open.failed', path=str(path)))
    return False
