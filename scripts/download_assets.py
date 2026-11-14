#!/usr/bin/env python3
"""Download all frontend assets once so the app runs fully offline.

Downloads:
- chess.js (ESM build)                          -> static/vendor/
- Inter + JetBrains Mono variable woff2         -> static/fonts/
- 12 chess piece SVGs (Cburnett set)            -> static/img/pieces/
- Lucide icon SVGs                              -> static/img/icons-src/ (built
                                                  into JS later by build_icons.py)

Everything is fetched from CDNs at build time only; the app itself never
touches the network. Re-run after changing ASSETS below.
"""
from __future__ import annotations

import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parent.parent
STATIC = ROOT / "static"

# ---------------------------------------------------------------- chess.js
CHESSJS_URL = "https://cdn.jsdelivr.net/npm/chess.js@1.4.0/dist/esm/chess.js"

# ------------------------------------------------------------------ fonts
# Variable (wght) builds; latin + cyrillic subsets for RU/EN UI.
FONT_URLS = {
    "inter-latin.woff2": "https://cdn.jsdelivr.net/fontsource/fonts/inter:vf@latest/latin-wght-normal.woff2",
    "inter-cyrillic.woff2": "https://cdn.jsdelivr.net/fontsource/fonts/inter:vf@latest/cyrillic-wght-normal.woff2",
    "jetbrains-mono-latin.woff2": "https://cdn.jsdelivr.net/fontsource/fonts/jetbrains-mono:vf@latest/latin-wght-normal.woff2",
    "jetbrains-mono-cyrillic.woff2": "https://cdn.jsdelivr.net/fontsource/fonts/jetbrains-mono:vf@latest/cyrillic-wght-normal.woff2",
}

# ----------------------------------------------------------------- pieces
# Cburnett SVG set (public domain standard chess pieces), prefer lichess repo.
LILA = "https://raw.githubusercontent.com/lichess-org/lila/master/public/piece/cburnett"
WIKI = "https://upload.wikimedia.org/wikipedia/commons"
PIECES = {
    "wK.svg": [f"{LILA}/wK.svg", f"{WIKI}/4/42/Chess_klt45.svg"],
    "wQ.svg": [f"{LILA}/wQ.svg", f"{WIKI}/1/15/Chess_qlt45.svg"],
    "wR.svg": [f"{LILA}/wR.svg", f"{WIKI}/7/72/Chess_rlt45.svg"],
    "wB.svg": [f"{LILA}/wB.svg", f"{WIKI}/b/b1/Chess_blt45.svg"],
    "wN.svg": [f"{LILA}/wN.svg", f"{WIKI}/7/70/Chess_nlt45.svg"],
    "wP.svg": [f"{LILA}/wP.svg", f"{WIKI}/4/45/Chess_plt45.svg"],
    "bK.svg": [f"{LILA}/bK.svg", f"{WIKI}/f/f0/Chess_kdt45.svg"],
    "bQ.svg": [f"{LILA}/bQ.svg", f"{WIKI}/4/47/Chess_qdt45.svg"],
    "bR.svg": [f"{LILA}/bR.svg", f"{WIKI}/f/ff/Chess_rdt45.svg"],
    "bB.svg": [f"{LILA}/bB.svg", f"{WIKI}/9/98/Chess_bdt45.svg"],
    "bN.svg": [f"{LILA}/bN.svg", f"{WIKI}/e/ef/Chess_ndt45.svg"],
    "bP.svg": [f"{LILA}/bP.svg", f"{WIKI}/c/c7/Chess_pdt45.svg"],
}

# ------------------------------------------------------------------ icons
# Lucide icons used across the UI (kebab-case file names).
LUCIDE = "https://cdn.jsdelivr.net/npm/lucide-static@0.544.0/icons"
ICONS = [
    "layout-dashboard", "cpu", "bot", "users", "user", "user-plus", "monitor-play",
    "history", "settings", "log-in", "log-out", "palette", "globe", "swords",
    "trophy", "medal", "clock", "timer", "volume-2", "volume-x", "eye", "eye-off",
    "download", "message-square", "send", "copy", "check", "x", "play", "rotate-ccw",
    "flag", "handshake", "chevron-left", "chevron-right", "chevrons-left",
    "chevrons-right", "chevron-down", "arrow-left", "sparkles", "wifi", "wifi-off",
    "zap", "triangle-alert", "info", "thermometer", "key-round", "server",
    "refresh-cw", "plus", "activity", "gauge", "lightbulb", "target", "flame",
    "crown", "shield", "menu", "sun", "moon", "star", "circle-help", "chart-line",
    "book-open", "brain", "trash-2", "external-link", "pipette",
    "undo-2", "list", "map-pin", "link", "sliders-horizontal", "save", "gauge", "type", "move",
]


def fetch(url: str, dest: Path, *, svg_check: bool = False) -> bool:
    import time as _time

    for attempt in range(4):
        try:
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            content = response.content
            if svg_check and b"<svg" not in content[:200]:
                return False
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(content)
            return True
        except requests.RequestException as exc:
            print(f"  !! attempt {attempt + 1}: {url} -> {exc}", file=sys.stderr)
            _time.sleep(1.5 * (attempt + 1))
    return False


def main() -> int:
    ok = True

    print("== chess.js ==")
    ok &= fetch(CHESSJS_URL, STATIC / "vendor" / "chess.js")

    print("== fonts ==")
    for name, url in FONT_URLS.items():
        ok &= fetch(url, STATIC / "fonts" / name)

    print("== pieces ==")
    pieces_dir = STATIC / "img" / "pieces"
    for name, urls in PIECES.items():
        dest = pieces_dir / name
        if dest.exists():
            continue
        got = False
        for url in urls:
            if fetch(url, dest, svg_check=True):
                got = True
                break
        ok &= got

    print("== lucide icons ==")
    icons_dir = STATIC / "img" / "icons-src"
    for name in ICONS:
        dest = icons_dir / f"{name}.svg"
        if dest.exists():
            continue
        if not fetch(f"{LUCIDE}/{name}.svg", dest, svg_check=True):
            print(f"  missing icon: {name}", file=sys.stderr)
            ok = False

    print("DONE" if ok else "SOME FAILED")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
