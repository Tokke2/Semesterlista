# FIL: plugins/lista/__init__.py

"""
Lista-plugin – Semesterlista & Limokörning.

Detta paket innehåller plugin för generering av semesterlistor
och limokörningsscheman i PDF-format.

UPPDATERAD v2.2.0: Synkad med plugin.py v2.2.0.
                   Manuell startmånad.
                   Standard = jan–dec valt år om inget väljs.
                   Manuellt val kan gå över årsskifte
                   (t.ex. dec 2026 → jan 2027).

copyright Rickard Längkvist 2025 – dynamiskt år
"""

__all__ = ["Plugin"]