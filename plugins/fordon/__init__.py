# FIL: plugins/fordon/__init__.py

"""
Fordonsplugin – egna flikar för fordon/limokörning.

Paketet innehåller en flik som återanvänder lista-pluginets vy och
PDF-generator men låser läget till "Limokörning" och använder
Fordon.txt som standardlista.

UPPDATERAD v2.5.0: Första versionen (flikar för hyra/semester/fordon).
                   SVG-logotyp från assets-mappen i PDF:en.

copyright Rickard Längkvist 2025 – dynamiskt år
"""

__all__ = ["Plugin"]
