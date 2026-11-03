"""
Temahantering – ThemeManager (3 teman: Mörkt, Ljust, System).

Detta modul hanterar applikationens utseende med exakt 3 teman.
Knappar och tabbar får alltid hög kontrast och fet text oavsett tema.

UPPDATERAD v2.2.0: Synkad med plugin.py v2.2.0 och settings_manager.py v2.2.0.
                   Inverterade knappar/tabbar vid tema-byte:
                     Ljust tema → Mörka knappar (#3D3D3D) med VIT fet text
                     Mörkt tema → Ljusa knappar (#E8E8E8) med SVART fet text
                   Alla knappar synliga, tydliga, FET text oavsett tema.

Färgspecifikationer:
    Ljust tema:
        Knapp-bakgrund:  #3D3D3D (mörkgrå)
        Knapp-text:      #FFFFFF (vit) FET
        Knapp-border:    #222222 (nästan svart)
        Tabb-bakgrund:   #4A4A4A (mörkgrå)
        Tabb-text:       #FFFFFF (vit) FET
        Tabb-active:     #0078D4 (blå accent)

    Mörkt tema:
        Knapp-bakgrund:  #E8E8E8 (ljusgrå)
        Knapp-text:      #000000 (svart) FET
        Knapp-border:    #AAAAAA (mellangrå)
        Tabb-bakgrund:   #D0D0D0 (ljusgrå)
        Tabb-text:       #000000 (svart) FET
        Tabb-active:     #0078D4 (blå accent)

Användning:
    from core.theme_manager import ThemeManager

    tm = ThemeManager(settings_manager)
    tm.set_theme("dark")
    qss = tm.get_button_tab_stylesheet()  # Applicera på widgets

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

import platform
import subprocess
from pathlib import Path
from typing import Dict, Optional, Tuple, TYPE_CHECKING

from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QPalette, QColor
from PySide6.QtCore import QObject, Signal

if TYPE_CHECKING:
    from core.settings_manager import SettingsManager

# ──────────────────────────────────────────────────────────
# Modulversion – synkad med APP_VERSION i main.py
# ──────────────────────────────────────────────────────────
MODULE_VERSION: str = "2.2.0"


class ThemeManager(QObject):
    """
    Hanterar 3 teman: dark, light, system.

    Princip för knappar och tabbar:
        Ljust tema → Mörka knappar med VIT text (inverterat mot bakgrund)
        Mörkt tema → Ljusa knappar med SVART text (inverterat mot bakgrund)

    Detta garanterar att knappar och tabbar ALLTID syns tydligt
    och har hög kontrast oavsett tema. FET text överallt.

    Signaler:
        theme_changed(str): Emitteras när temat ändras.
                            Data: "dark", "light" eller "system".
    """

    # ──────────────────────────────────────────────────────────
    # Signaler
    # ──────────────────────────────────────────────────────────

    theme_changed = Signal(str)

    # ──────────────────────────────────────────────────────────
    # Temakonstanter
    # ──────────────────────────────────────────────────────────

    DARK_THEME:   str = "dark"
    LIGHT_THEME:  str = "light"
    SYSTEM_THEME: str = "system"

    VALID_THEMES: Tuple[str, str, str] = (DARK_THEME, LIGHT_THEME, SYSTEM_THEME)

    # ──────────────────────────────────────────────────────────
    # Färgdefinitioner – LJUST TEMA
    # ──────────────────────────────────────────────────────────
    # Princip: Ljus fönsterbakgrund → MÖRKA knappar med VIT text.
    # Knappar och tabbar inverteras mot bakgrunden för maximal synlighet.
    # ──────────────────────────────────────────────────────────

    LIGHT_COLORS: Dict[str, str] = {
        # ── Knappar – MÖRKA med VIT text ──────────────────
        "button_bg":           "#3D3D3D",   # Mörkgrå – syns mot ljus bg
        "button_fg":           "#FFFFFF",   # Vit – hög kontrast
        "button_border":       "#222222",   # Nästan svart ram
        "button_hover_bg":     "#555555",   # Ljusare mörkgrå vid hover
        "button_hover_border": "#0078D4",   # Blå accent vid hover
        "button_pressed_bg":   "#2A2A2A",   # Mörkare vid tryck
        "button_disabled_bg":  "#CCCCCC",   # Grå vid inaktiv
        "button_disabled_fg":  "#888888",   # Mellangrå text
        # ── Tabbar – MÖRKA med VIT text ───────────────────
        "tab_bg":              "#4A4A4A",   # Mörkgrå – syns mot ljus bg
        "tab_fg":              "#FFFFFF",   # Vit – hög kontrast
        "tab_hover_bg":        "#5E5E5E",   # Ljusare mörkgrå vid hover
        "tab_selected_bg":     "#0078D4",   # Blå accent (aktiv tabb)
        "tab_selected_fg":     "#FFFFFF",   # Vit text på aktiv
        "tab_border":          "#333333",   # Mörk ram
        # ── Fönster/text ───────────────────────────────────
        "window_bg":           "#FAFAFA",   # Nästan vit
        "window_fg":           "#1A1A1A",   # Nästan svart
        # ── Accent ─────────────────────────────────────────
        "accent":              "#0078D4",   # Blå
        "accent_hover":        "#1084E8",   # Ljusare blå
        # ── Scrollbar ──────────────────────────────────────
        "scrollbar_bg":        "#D0D0D0",
        "scrollbar_handle":    "#909090",
        # ── Meny ───────────────────────────────────────────
        "menu_bg":             "#F5F5F5",
        "menu_fg":             "#1A1A1A",
        "menu_hover_bg":       "#0078D4",
        "menu_hover_fg":       "#FFFFFF",
        # ── Statusrad ──────────────────────────────────────
        "statusbar_bg":        "#E8E8E8",
        "statusbar_fg":        "#333333",
        # ── Inmatningsfält ─────────────────────────────────
        "input_bg":            "#FFFFFF",
        "input_fg":            "#1A1A1A",
        "input_border":        "#CCCCCC",
        "input_focus_border":  "#0078D4",
    }

    # ──────────────────────────────────────────────────────────
    # Färgdefinitioner – MÖRKT TEMA
    # ──────────────────────────────────────────────────────────
    # Princip: Mörk fönsterbakgrund → LJUSA knappar med SVART text.
    # Knappar och tabbar inverteras mot bakgrunden för maximal synlighet.
    # ──────────────────────────────────────────────────────────

    DARK_COLORS: Dict[str, str] = {
        # ── Knappar – LJUSA med SVART text ────────────────
        "button_bg":           "#E8E8E8",   # Ljusgrå – syns mot mörk bg
        "button_fg":           "#000000",   # Svart – hög kontrast
        "button_border":       "#AAAAAA",   # Mellangrå ram
        "button_hover_bg":     "#FFFFFF",   # Vit vid hover
        "button_hover_border": "#0078D4",   # Blå accent vid hover
        "button_pressed_bg":   "#C8C8C8",   # Mörkare ljusgrå vid tryck
        "button_disabled_bg":  "#555555",   # Mörkgrå vid inaktiv
        "button_disabled_fg":  "#888888",   # Grå text
        # ── Tabbar – LJUSA med SVART text ─────────────────
        "tab_bg":              "#D0D0D0",   # Ljusgrå – syns mot mörk bg
        "tab_fg":              "#000000",   # Svart – hög kontrast
        "tab_hover_bg":        "#E8E8E8",   # Ljusare vid hover
        "tab_selected_bg":     "#0078D4",   # Blå accent (aktiv tabb)
        "tab_selected_fg":     "#FFFFFF",   # Vit text på aktiv
        "tab_border":          "#888888",   # Mellangrå ram
        # ── Fönster/text ───────────────────────────────────
        "window_bg":           "#1A1A1A",   # Mörk
        "window_fg":           "#E8E8E8",   # Ljus
        # ── Accent ─────────────────────────────────────────
        "accent":              "#0078D4",   # Blå
        "accent_hover":        "#1084E8",   # Ljusare blå
        # ── Scrollbar ──────────────────────────────────────
        "scrollbar_bg":        "#3A3A3A",
        "scrollbar_handle":    "#6A6A6A",
        # ── Meny ───────────────────────────────────────────
        "menu_bg":             "#2D2D2D",
        "menu_fg":             "#E8E8E8",
        "menu_hover_bg":       "#0078D4",
        "menu_hover_fg":       "#FFFFFF",
        # ── Statusrad ──────────────────────────────────────
        "statusbar_bg":        "#252525",
        "statusbar_fg":        "#CCCCCC",
        # ── Inmatningsfält ─────────────────────────────────
        "input_bg":            "#2D2D2D",
        "input_fg":            "#E8E8E8",
        "input_border":        "#555555",
        "input_focus_border":  "#0078D4",
    }

    # ──────────────────────────────────────────────────────────
    # Konstruktor
    # ──────────────────────────────────────────────────────────

    def __init__(self, settings_manager: "SettingsManager"):
        """
        Initiera ThemeManager.

        Laddar sparat tema från SettingsManager. Om inget tema är
        sparat används "system" som standard.

        Args:
            settings_manager: Applikationens SettingsManager-instans.
        """
        super().__init__()

        self._settings_manager: "SettingsManager" = settings_manager
        self._current_theme:    str               = self.SYSTEM_THEME
        self._current_colors:   Dict[str, str]    = dict(self.LIGHT_COLORS)

        # Ladda sparat tema
        saved_theme = self._settings_manager.get("theme", self.SYSTEM_THEME)
        if saved_theme in self.VALID_THEMES:
            self._current_theme = saved_theme

    # ──────────────────────────────────────────────────────────
    # Publika metoder
    # ──────────────────────────────────────────────────────────

    def get_current_theme(self) -> str:
        """Returnera aktuellt tema: dark, light eller system."""
        return self._current_theme

    def get_version(self) -> str:
        """Returnera modulens versionsnummer."""
        return MODULE_VERSION

    def is_dark(self) -> bool:
        """Returnera True om aktuellt effektivt tema är mörkt."""
        if self._current_theme == self.DARK_THEME:
            return True
        if self._current_theme == self.SYSTEM_THEME:
            return self._detect_system_theme() == self.DARK_THEME
        return False

    def set_theme(self, theme: str) -> None:
        """
        Sätt nytt tema och applicera det omedelbart.

        Knappar och tabbar inverteras automatiskt:
            Ljust tema → Mörka knappar med vit text
            Mörkt tema → Ljusa knappar med svart text

        Args:
            theme: "dark", "light" eller "system".

        Raises:
            ValueError: Om temat inte är ett av de 3 tillåtna.
        """
        if theme not in self.VALID_THEMES:
            raise ValueError(
                f"Ogiltigt tema: '{theme}'. "
                f"Tillåtna: {self.VALID_THEMES}"
            )

        if theme == self._current_theme and theme != self.SYSTEM_THEME:
            return

        self._current_theme = theme
        self._apply_current_theme()
        self._settings_manager.set("theme", theme)
        self.theme_changed.emit(theme)

    def refresh(self) -> None:
        """Återapplicera aktuellt tema (t.ex. efter systeminst. ändrats)."""
        self._apply_current_theme()

    # ──────────────────────────────────────────────────────────
    # Applicering av teman (internt)
    # ──────────────────────────────────────────────────────────

    def _apply_current_theme(self) -> None:
        """
        Applicera aktuellt tema på QApplication.

        Ordning:
          1. Sätt rätt _current_colors (dark/light)
          2. Bygg QPalette
          3. Applicera stylesheet (get_button_tab_stylesheet)
          4. Om extern QSS-fil finns – applicera den ovanpå
        """
        app = QApplication.instance()
        if app is None:
            return

        effective = self._get_effective_theme()

        if effective == self.DARK_THEME:
            self._apply_dark_theme(app)
        else:
            self._apply_light_theme(app)

        # Applicera alltid komplett stylesheet –
        # säkerställer att knappar/tabbar är korrekt inverterade
        app.setStyleSheet(self.get_button_tab_stylesheet())

    def _get_effective_theme(self) -> str:
        """Returnera effektivt tema (dark/light). Löser upp system→OS."""
        if self._current_theme == self.SYSTEM_THEME:
            return self._detect_system_theme()
        return self._current_theme

    def _apply_dark_theme(self, app: QApplication) -> None:
        """
        Applicera mörkt tema.

        Knappar/tabbar = LJUSA med SVART text (inverterade mot mörk bg).
        """
        self._current_colors = dict(self.DARK_COLORS)
        palette = self._get_base_palette(is_dark=True)
        app.setPalette(palette)
        # Försök ladda extern QSS som tillägg
        qss = self._load_qss_file("dark.qss")
        if qss:
            app.setStyleSheet(qss + "\n" + self.get_button_tab_stylesheet())

    def _apply_light_theme(self, app: QApplication) -> None:
        """
        Applicera ljust tema.

        Knappar/tabbar = MÖRKA med VIT text (inverterade mot ljus bg).
        """
        self._current_colors = dict(self.LIGHT_COLORS)
        palette = self._get_base_palette(is_dark=False)
        app.setPalette(palette)
        # Försök ladda extern QSS som tillägg
        qss = self._load_qss_file("light.qss")
        if qss:
            app.setStyleSheet(qss + "\n" + self.get_button_tab_stylesheet())

    # ──────────────────────────────────────────────────────────
    # System-tema-detektering
    # ──────────────────────────────────────────────────────────

    def _detect_system_theme(self) -> str:
        """Detektera operativsystemets tema (dark/light)."""
        system = platform.system()
        try:
            if system == "Windows":
                return self._detect_windows_theme()
            elif system == "Darwin":
                return self._detect_macos_theme()
            else:
                return self._detect_linux_theme()
        except Exception:
            return self.LIGHT_THEME

    def _detect_windows_theme(self) -> str:
        """Detektera Windows-tema via registret."""
        try:
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion"
                r"\Themes\Personalize",
            )
            value, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
            winreg.CloseKey(key)
            return self.LIGHT_THEME if value == 1 else self.DARK_THEME
        except Exception:
            return self.LIGHT_THEME

    def _detect_macos_theme(self) -> str:
        """Detektera macOS-tema via defaults-kommandot."""
        try:
            result = subprocess.run(
                ["defaults", "read", "-g", "AppleInterfaceStyle"],
                capture_output=True,
                text=True,
                timeout=2,
            )
            return (
                self.DARK_THEME
                if "Dark" in result.stdout
                else self.LIGHT_THEME
            )
        except Exception:
            return self.LIGHT_THEME

    def _detect_linux_theme(self) -> str:
        """Detektera Linux-tema via gsettings (GNOME) eller KDE."""
        try:
            result = subprocess.run(
                [
                    "gsettings", "get",
                    "org.gnome.desktop.interface",
                    "gtk-theme",
                ],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if "dark" in result.stdout.lower():
                return self.DARK_THEME

            result2 = subprocess.run(
                [
                    "gsettings", "get",
                    "org.gnome.desktop.interface",
                    "color-scheme",
                ],
                capture_output=True,
                text=True,
                timeout=2,
            )
            if "dark" in result2.stdout.lower():
                return self.DARK_THEME

            return self.LIGHT_THEME

        except Exception:
            # Fallback: försök KDE kdeglobals
            try:
                kde_config = Path.home() / ".config" / "kdeglobals"
                if kde_config.exists():
                    content = kde_config.read_text(encoding="utf-8")
                    for line in content.split("\n"):
                        if "ColorScheme=" in line:
                            if "dark" in line.lower():
                                return self.DARK_THEME
                            break
            except Exception:
                pass
            return self.LIGHT_THEME

    # ──────────────────────────────────────────────────────────
    # Färg-hjälpare (publika)
    # ──────────────────────────────────────────────────────────

    def get_button_color(self) -> Tuple[str, str, str]:
        """
        Returnera (bakgrund, text, border) för knappar.

        Ljust tema → ("#3D3D3D", "#FFFFFF", "#222222")
        Mörkt tema → ("#E8E8E8", "#000000", "#AAAAAA")
        """
        c = self._current_colors
        return (c["button_bg"], c["button_fg"], c["button_border"])

    def get_tab_color(self) -> Tuple[str, str]:
        """
        Returnera (bakgrund, text) för tabbar.

        Ljust tema → ("#4A4A4A", "#FFFFFF")
        Mörkt tema → ("#D0D0D0", "#000000")
        """
        c = self._current_colors
        return (c["tab_bg"], c["tab_fg"])

    def get_color(self, key: str) -> str:
        """Hämta specifik färg från aktuellt tema via nyckel."""
        return self._current_colors.get(key, "")

    def get_all_colors(self) -> Dict[str, str]:
        """Returnera alla färger för aktuellt tema som dict."""
        return dict(self._current_colors)

    # ──────────────────────────────────────────────────────────
    # QPalette-byggare
    # ──────────────────────────────────────────────────────────

    def _get_base_palette(self, is_dark: bool) -> QPalette:
        """
        Bygg grundläggande QPalette för mörkt eller ljust tema.

        OBS: QPalette påverkar grundwidgets men QSS:en
        (get_button_tab_stylesheet) tar över för knappar/tabbar.
        """
        palette = QPalette()

        if is_dark:
            # ── Mörkt tema ─────────────────────────────────
            palette.setColor(QPalette.ColorRole.Window,          QColor("#1A1A1A"))
            palette.setColor(QPalette.ColorRole.WindowText,      QColor("#E8E8E8"))
            palette.setColor(QPalette.ColorRole.Base,            QColor("#2D2D2D"))
            palette.setColor(QPalette.ColorRole.AlternateBase,   QColor("#353535"))
            palette.setColor(QPalette.ColorRole.ToolTipBase,     QColor("#3A3A3A"))
            palette.setColor(QPalette.ColorRole.ToolTipText,     QColor("#E8E8E8"))
            palette.setColor(QPalette.ColorRole.Text,            QColor("#E8E8E8"))
            palette.setColor(QPalette.ColorRole.Button,          QColor("#E8E8E8"))
            palette.setColor(QPalette.ColorRole.ButtonText,      QColor("#000000"))
            palette.setColor(QPalette.ColorRole.BrightText,      QColor("#FF4444"))
            palette.setColor(QPalette.ColorRole.Link,            QColor("#0078D4"))
            palette.setColor(QPalette.ColorRole.Highlight,       QColor("#0078D4"))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
            # Disabled
            palette.setColor(
                QPalette.ColorGroup.Disabled,
                QPalette.ColorRole.WindowText, QColor("#888888"),
            )
            palette.setColor(
                QPalette.ColorGroup.Disabled,
                QPalette.ColorRole.Text, QColor("#888888"),
            )
            palette.setColor(
                QPalette.ColorGroup.Disabled,
                QPalette.ColorRole.ButtonText, QColor("#888888"),
            )
        else:
            # ── Ljust tema ─────────────────────────────────
            palette.setColor(QPalette.ColorRole.Window,          QColor("#FAFAFA"))
            palette.setColor(QPalette.ColorRole.WindowText,      QColor("#1A1A1A"))
            palette.setColor(QPalette.ColorRole.Base,            QColor("#FFFFFF"))
            palette.setColor(QPalette.ColorRole.AlternateBase,   QColor("#F5F5F5"))
            palette.setColor(QPalette.ColorRole.ToolTipBase,     QColor("#FFFFDC"))
            palette.setColor(QPalette.ColorRole.ToolTipText,     QColor("#1A1A1A"))
            palette.setColor(QPalette.ColorRole.Text,            QColor("#1A1A1A"))
            palette.setColor(QPalette.ColorRole.Button,          QColor("#3D3D3D"))
            palette.setColor(QPalette.ColorRole.ButtonText,      QColor("#FFFFFF"))
            palette.setColor(QPalette.ColorRole.BrightText,      QColor("#CC0000"))
            palette.setColor(QPalette.ColorRole.Link,            QColor("#0078D4"))
            palette.setColor(QPalette.ColorRole.Highlight,       QColor("#0078D4"))
            palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
            # Disabled
            palette.setColor(
                QPalette.ColorGroup.Disabled,
                QPalette.ColorRole.WindowText, QColor("#AAAAAA"),
            )
            palette.setColor(
                QPalette.ColorGroup.Disabled,
                QPalette.ColorRole.Text, QColor("#AAAAAA"),
            )
            palette.setColor(
                QPalette.ColorGroup.Disabled,
                QPalette.ColorRole.ButtonText, QColor("#AAAAAA"),
            )

        return palette

    # ──────────────────────────────────────────────────────────
    # QSS-fil-laddning
    # ──────────────────────────────────────────────────────────

    def _load_qss_file(self, filename: str) -> Optional[str]:
        """
        Ladda QSS-fil från resources/themes/.

        Returnerar filinnehållet, eller None om filen saknas.
        """
        try:
            qss_path = (
                Path(__file__).parent.parent
                / "resources"
                / "themes"
                / filename
            )
            if qss_path.exists():
                return qss_path.read_text(encoding="utf-8")
        except Exception:
            pass
        return None

    # ──────────────────────────────────────────────────────────
    # QSS-stylesheet (huvud-generator)
    # ──────────────────────────────────────────────────────────

    def get_button_tab_stylesheet(self) -> str:
        """
        Bygg och returnera komplett QSS-sträng för hela applikationen.

        Garantier:
          - ALL text i QPushButton, QToolButton, QTabBar är FET
          - Ljust tema → Mörka knappar/tabbar med VIT text
          - Mörkt tema → Ljusa knappar/tabbar med SVART text
          - Hover, pressed, disabled, selected – alla tillstånd täckta
          - Scrollbar, meny, statusbar, groupbox, input, checkbox, label
          - Inget tillstånd lämnar knappar/tabbar oläsliga
        """
        c = self._current_colors

        return f"""
/* ═══════════════════════════════════════════════════════════
   QSS – ThemeManager v{MODULE_VERSION}
   Tema: {self._current_theme}
   Knappar inverterade: ljust→mörka knappar, mörkt→ljusa knappar
   ALL knapp/tabb-text: font-weight: bold
   ═══════════════════════════════════════════════════════════ */

/* ── QPushButton ────────────────────────────────────────── */

QPushButton {{
    background-color: {c["button_bg"]};
    color: {c["button_fg"]};
    border: 2px solid {c["button_border"]};
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: bold;
    font-size: 13px;
    min-height: 32px;
    min-width: 80px;
}}

QPushButton:hover {{
    background-color: {c["button_hover_bg"]};
    color: {c["button_fg"]};
    border: 2px solid {c["button_hover_border"]};
    font-weight: bold;
}}

QPushButton:pressed {{
    background-color: {c["button_pressed_bg"]};
    color: {c["button_fg"]};
    border: 2px solid {c["accent"]};
    padding: 9px 19px 7px 21px;
    font-weight: bold;
}}

QPushButton:disabled {{
    background-color: {c["button_disabled_bg"]};
    color: {c["button_disabled_fg"]};
    border: 2px solid {c["button_disabled_bg"]};
    font-weight: bold;
}}

QPushButton:checked {{
    background-color: {c["accent"]};
    color: #FFFFFF;
    border: 2px solid {c["accent"]};
    font-weight: bold;
}}

QPushButton:focus {{
    border: 2px solid {c["accent"]};
    outline: none;
}}

/* ── QToolButton ────────────────────────────────────────── */

QToolButton {{
    background-color: {c["button_bg"]};
    color: {c["button_fg"]};
    border: 2px solid {c["button_border"]};
    border-radius: 5px;
    padding: 6px 12px;
    font-weight: bold;
    font-size: 12px;
    min-height: 28px;
}}

QToolButton:hover {{
    background-color: {c["button_hover_bg"]};
    color: {c["button_fg"]};
    border: 2px solid {c["button_hover_border"]};
    font-weight: bold;
}}

QToolButton:pressed {{
    background-color: {c["button_pressed_bg"]};
    color: {c["button_fg"]};
    font-weight: bold;
}}

QToolButton:disabled {{
    background-color: {c["button_disabled_bg"]};
    color: {c["button_disabled_fg"]};
    font-weight: bold;
}}

/* ── QTabBar::tab ───────────────────────────────────────── */

QTabBar::tab {{
    background-color: {c["tab_bg"]};
    color: {c["tab_fg"]};
    border: 1px solid {c["tab_border"]};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    padding: 10px 22px;
    margin-right: 3px;
    font-weight: bold;
    font-size: 12px;
    min-width: 90px;
}}

QTabBar::tab:hover {{
    background-color: {c["tab_hover_bg"]};
    color: {c["tab_fg"]};
    border: 1px solid {c["accent"]};
    border-bottom: none;
    font-weight: bold;
}}

QTabBar::tab:selected {{
    background-color: {c["tab_selected_bg"]};
    color: {c["tab_selected_fg"]};
    border: 1px solid {c["tab_selected_bg"]};
    border-bottom: 4px solid {c["accent"]};
    padding: 10px 22px 6px 22px;
    font-weight: bold;
}}

QTabBar::tab:disabled {{
    background-color: {c["button_disabled_bg"]};
    color: {c["button_disabled_fg"]};
    font-weight: bold;
}}

/* ── QTabWidget ─────────────────────────────────────────── */

QTabWidget::pane {{
    border: 1px solid {c["tab_border"]};
    border-radius: 4px;
    background-color: {c["window_bg"]};
    top: -1px;
}}

QTabBar {{ qproperty-drawBase: 0; }}

/* ── QTabBar scroll-knappar ─────────────────────────────── */

QTabBar::scroller {{ width: 28px; }}

QTabBar QToolButton {{
    background-color: {c["tab_bg"]};
    color: {c["tab_fg"]};
    border: 1px solid {c["tab_border"]};
    border-radius: 3px;
    padding: 4px;
    font-weight: bold;
    min-height: 24px;
}}

QTabBar QToolButton:hover {{
    background-color: {c["tab_hover_bg"]};
    color: {c["tab_fg"]};
    font-weight: bold;
}}

/* ── QScrollBar (mushjulsscroll) ────────────────────────── */

QScrollBar:vertical {{
    background: {c["scrollbar_bg"]};
    width: 14px;
    margin: 0;
    border-radius: 7px;
}}

QScrollBar::handle:vertical {{
    background: {c["scrollbar_handle"]};
    min-height: 30px;
    border-radius: 7px;
}}

QScrollBar::handle:vertical:hover {{
    background: {c["accent"]};
}}

QScrollBar::add-line:vertical,
QScrollBar::sub-line:vertical {{
    height: 0;
    border: none;
}}

QScrollBar:horizontal {{
    background: {c["scrollbar_bg"]};
    height: 14px;
    margin: 0;
    border-radius: 7px;
}}

QScrollBar::handle:horizontal {{
    background: {c["scrollbar_handle"]};
    min-width: 30px;
    border-radius: 7px;
}}

QScrollBar::handle:horizontal:hover {{
    background: {c["accent"]};
}}

QScrollBar::add-line:horizontal,
QScrollBar::sub-line:horizontal {{
    width: 0;
    border: none;
}}

/* ── QMenu ──────────────────────────────────────────────── */

QMenu {{
    background-color: {c["menu_bg"]};
    color: {c["menu_fg"]};
    border: 1px solid {c["tab_border"]};
    border-radius: 5px;
    padding: 6px 0;
    font-weight: bold;
    font-size: 12px;
}}

QMenu::item {{
    padding: 8px 32px 8px 14px;
    border-radius: 3px;
    font-weight: bold;
}}

QMenu::item:selected {{
    background-color: {c["menu_hover_bg"]};
    color: {c["menu_hover_fg"]};
    font-weight: bold;
}}

QMenu::separator {{
    height: 1px;
    background: {c["tab_border"]};
    margin: 4px 10px;
}}

/* ── QMenuBar ───────────────────────────────────────────── */

QMenuBar {{
    background-color: {c["window_bg"]};
    color: {c["window_fg"]};
    border-bottom: 1px solid {c["tab_border"]};
    font-weight: bold;
    font-size: 12px;
    padding: 2px;
}}

QMenuBar::item {{
    padding: 6px 14px;
    border-radius: 4px;
    font-weight: bold;
}}

QMenuBar::item:selected {{
    background-color: {c["accent"]};
    color: #FFFFFF;
    font-weight: bold;
}}

QMenuBar::item:pressed {{
    background-color: {c["accent"]};
    color: #FFFFFF;
    font-weight: bold;
}}

/* ── QStatusBar ─────────────────────────────────────────── */

QStatusBar {{
    background-color: {c["statusbar_bg"]};
    color: {c["statusbar_fg"]};
    border-top: 1px solid {c["tab_border"]};
    padding: 4px 10px;
    font-size: 11px;
    font-weight: bold;
}}

/* ── QGroupBox ──────────────────────────────────────────── */

QGroupBox {{
    border: 1px solid {c["tab_border"]};
    border-radius: 6px;
    margin-top: 16px;
    padding-top: 16px;
    font-weight: bold;
    color: {c["window_fg"]};
    font-size: 12px;
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    padding: 0 10px;
    background-color: {c["window_bg"]};
    font-weight: bold;
    color: {c["window_fg"]};
}}

/* ── QLineEdit / QSpinBox / QDoubleSpinBox / QComboBox ─── */

QLineEdit,
QSpinBox,
QDoubleSpinBox,
QComboBox {{
    border: 2px solid {c["input_border"]};
    border-radius: 5px;
    padding: 6px 10px;
    background-color: {c["input_bg"]};
    color: {c["input_fg"]};
    min-height: 24px;
    font-size: 12px;
    font-weight: bold;
}}

QLineEdit:focus,
QSpinBox:focus,
QDoubleSpinBox:focus,
QComboBox:focus {{
    border: 2px solid {c["input_focus_border"]};
}}

QLineEdit:disabled,
QSpinBox:disabled,
QDoubleSpinBox:disabled,
QComboBox:disabled {{
    background-color: {c["button_disabled_bg"]};
    color: {c["button_disabled_fg"]};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 28px;
    border-left: 1px solid {c["tab_border"]};
    border-top-right-radius: 5px;
    border-bottom-right-radius: 5px;
    background-color: {c["button_bg"]};
}}

QComboBox::down-arrow {{
    width: 12px;
    height: 12px;
}}

QComboBox QAbstractItemView {{
    background-color: {c["menu_bg"]};
    color: {c["menu_fg"]};
    selection-background-color: {c["accent"]};
    selection-color: #FFFFFF;
    border: 1px solid {c["tab_border"]};
    border-radius: 3px;
    font-weight: bold;
    font-size: 12px;
    padding: 4px;
}}

QSpinBox::up-button,
QSpinBox::down-button {{
    background-color: {c["button_bg"]};
    border: 1px solid {c["button_border"]};
    width: 18px;
}}

QSpinBox::up-button:hover,
QSpinBox::down-button:hover {{
    background-color: {c["button_hover_bg"]};
}}

/* ── QCheckBox ──────────────────────────────────────────── */

QCheckBox {{
    color: {c["window_fg"]};
    spacing: 8px;
    font-weight: bold;
    font-size: 12px;
}}

QCheckBox::indicator {{
    width: 20px;
    height: 20px;
    border: 2px solid {c["tab_border"]};
    border-radius: 4px;
    background-color: {c["input_bg"]};
}}

QCheckBox::indicator:hover {{
    border: 2px solid {c["accent"]};
}}

QCheckBox::indicator:checked {{
    background-color: {c["accent"]};
    border: 2px solid {c["accent"]};
}}

QCheckBox::indicator:disabled {{
    background-color: {c["button_disabled_bg"]};
    border: 2px solid {c["button_disabled_bg"]};
}}

/* ── QLabel ─────────────────────────────────────────────── */

QLabel {{
    color: {c["window_fg"]};
    font-size: 12px;
}}

QLabel[heading="true"] {{
    font-weight: bold;
    font-size: 14px;
    color: {c["window_fg"]};
}}

QLabel[link="true"] {{
    color: {c["accent"]};
    text-decoration: underline;
    font-weight: bold;
}}

/* ── QFrame / kort-widget ───────────────────────────────── */

QFrame[card="true"] {{
    border: 1px solid {c["tab_border"]};
    border-radius: 6px;
    padding: 8px;
    background-color: {c["window_bg"]};
}}

/* ── QProgressBar ───────────────────────────────────────── */

QProgressBar {{
    border: 2px solid {c["tab_border"]};
    border-radius: 5px;
    text-align: center;
    font-weight: bold;
    font-size: 11px;
    height: 22px;
    color: {c["window_fg"]};
    background-color: {c["input_bg"]};
}}

QProgressBar::chunk {{
    background-color: {c["accent"]};
    border-radius: 3px;
}}

/* ── QDialog ────────────────────────────────────────────── */

QDialog {{
    background-color: {c["window_bg"]};
    color: {c["window_fg"]};
}}

/* ── QDialogButtonBox ───────────────────────────────────── */

QDialogButtonBox QPushButton {{
    background-color: {c["button_bg"]};
    color: {c["button_fg"]};
    border: 2px solid {c["button_border"]};
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: bold;
    font-size: 13px;
    min-height: 32px;
    min-width: 80px;
}}

QDialogButtonBox QPushButton:hover {{
    background-color: {c["button_hover_bg"]};
    border: 2px solid {c["button_hover_border"]};
    font-weight: bold;
}}

QDialogButtonBox QPushButton:pressed {{
    background-color: {c["button_pressed_bg"]};
    font-weight: bold;
}}

/* ── QMessageBox ────────────────────────────────────────── */

QMessageBox {{
    background-color: {c["window_bg"]};
    color: {c["window_fg"]};
}}

QMessageBox QPushButton {{
    background-color: {c["button_bg"]};
    color: {c["button_fg"]};
    border: 2px solid {c["button_border"]};
    border-radius: 6px;
    padding: 8px 20px;
    font-weight: bold;
    font-size: 13px;
    min-height: 32px;
    min-width: 80px;
}}

QMessageBox QPushButton:hover {{
    background-color: {c["button_hover_bg"]};
    border: 2px solid {c["button_hover_border"]};
    font-weight: bold;
}}

/* ── QMainWindow / QWidget (baswidget) ──────────────────── */

QMainWindow,
QWidget {{
    background-color: {c["window_bg"]};
    color: {c["window_fg"]};
}}

/* ── QToolTip ───────────────────────────────────────────── */

QToolTip {{
    background-color: {c["menu_bg"]};
    color: {c["menu_fg"]};
    border: 1px solid {c["tab_border"]};
    border-radius: 4px;
    padding: 6px 10px;
    font-size: 11px;
    font-weight: bold;
}}
"""