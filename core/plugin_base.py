"""
Bakåtkompatibel brygga – re-exporterar BasePlugin från plugins/.

Denna fil finns för att stödja plugins som importerar från
core.plugin_base (gammal sökväg). All ny kod bör importera från
plugins.base_plugin direkt.

UPPDATERAD v2.2.0: Synkad med plugins/base_plugin.py v2.2.0.

Användning (gammal stil – fungerar fortfarande):
    from core.plugin_base import PluginBase

Användning (ny stil – rekommenderad):
    from plugins.base_plugin import BasePlugin

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from plugins.base_plugin import BasePlugin

# Alias för bakåtkompatibilitet
PluginBase = BasePlugin

__all__ = ["BasePlugin", "PluginBase"]