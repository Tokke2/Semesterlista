#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fönstrets placering på skärmen (v2.11.0)
========================================

Huvudfönstrets geometri sparas i ``settings.json`` och återställs vid start.
Problemet: sparar man fönstret på en extra skärm som sedan kopplas bort (eller
byter upplösning) hamnar fönstret **utanför** den synliga ytan – appen startar
men syns inte.

Den här modulen håller den rena beräkningen (``clamp_geometry``) så att den
kan testas utan Qt:

    from core.window_state import clamp_geometry

    x, y, w, h = clamp_geometry(x, y, w, h, [(0, 0, 1920, 1040)])

Modulen är medveten om marginaler: minst ``MIN_VISIBLE_W`` × ``MIN_VISIBLE_H``
punkter av fönstret måste ligga innanför en skärm, annars centreras fönstret
på den första (primära) skärmen.

copyright Rickard Längkvist 2025 – dynamiskt år
"""

from __future__ import annotations

from typing import Sequence, Tuple

MODULE_VERSION: str = "2.17.2"

#: Minsta storlek som alltid tillåts (samma som MainWindow.setMinimumSize)
MIN_WIDTH: int = 800
MIN_HEIGHT: int = 600

#: Hur mycket av fönstret som minst måste synas för att placeringen godtas
MIN_VISIBLE_W: int = 160
MIN_VISIBLE_H: int = 60

Rect = Tuple[int, int, int, int]


def _intersection(a: Rect, b: Rect) -> Tuple[int, int]:
    """Bredd och höjd på överlappningen mellan två rektanglar."""
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    left = max(ax, bx)
    top = max(ay, by)
    right = min(ax + aw, bx + bw)
    bottom = min(ay + ah, by + bh)
    return max(0, right - left), max(0, bottom - top)


def clamp_geometry(
    x: int,
    y: int,
    width: int,
    height: int,
    screens: Sequence[Rect],
    min_width: int = MIN_WIDTH,
    min_height: int = MIN_HEIGHT,
) -> Rect:
    """
    Justera fönstrets geometri så att det syns på en skärm.

    Args:
        x, y:          Sparad position.
        width, height: Sparad storlek.
        screens:       Synliga ytor som ``(x, y, bredd, höjd)`` – t.ex.
                       ``QScreen.availableGeometry()`` för varje skärm.
        min_width / min_height: Minsta tillåtna storlek.

    Returns:
        ``(x, y, bredd, höjd)`` som garanterat har minst ``MIN_VISIBLE_W`` ×
        ``MIN_VISIBLE_H`` punkter innanför någon skärm.

    Exempel:
        >>> clamp_geometry(5000, 3000, 1200, 800, [(0, 0, 1920, 1040)])
        (360, 120, 1200, 800)
    """
    if not screens:
        # Utan kännedom om skärmarna: rör inget
        return int(x), int(y), max(int(width), int(min_width)), max(int(height), int(min_height))

    w = max(int(width), int(min_width))
    h = max(int(height), int(min_height))

    window = (int(x), int(y), w, h)
    for screen in screens:
        visible_w, visible_h = _intersection(window, screen)
        if visible_w >= MIN_VISIBLE_W and visible_h >= MIN_VISIBLE_H:
            return window

    # Placeringen syns inte – centrera på den första (primära) skärmen
    sx, sy, sw, sh = screens[0]
    cx = sx + max(0, (sw - w) // 2)
    cy = sy + max(0, (sh - h) // 2)

    # Om fönstret är större än skärmen: ankra i skärmens övre vänstra hörn
    cx = min(cx, sx + max(0, sw - MIN_VISIBLE_W))
    cy = min(cy, sy + max(0, sh - MIN_VISIBLE_H))
    return max(sx, cx), max(sy, cy), w, h


__all__ = [
    "MIN_HEIGHT",
    "MIN_VISIBLE_H",
    "MIN_VISIBLE_W",
    "MIN_WIDTH",
    "MODULE_VERSION",
    "clamp_geometry",
]
