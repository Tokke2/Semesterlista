"""Selected bilingual PDF headings without changing the application language."""
from core import i18n


def month_label(month, settings, compact=False):
    if settings.get('pdf_bilingual', False):
        kind = 'short' if compact else 'long'
        return ' / '.join(i18n.MONTH_NAMES[lang][kind][month - 1] for lang in ('sv', 'en'))
    return i18n.month_name(month)


def weekdays(settings):
    if settings.get('pdf_bilingual', False):
        return [i18n.WEEKDAY_NAMES['sv']['short'][i] + '/' + i18n.WEEKDAY_NAMES['en']['short'][i]
                for i in range(7)]
    return i18n.weekday_short_names()
