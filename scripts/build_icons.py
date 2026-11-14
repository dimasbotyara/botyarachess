#!/usr/bin/env python3
"""Build static/js/core/icons.js from the downloaded Lucide SVGs.

Stores the inner markup of each icon and emits an ES module with an
icon(name, cls) helper -> inline <svg> using currentColor, so icons follow
the active theme automatically. Re-run after downloading new icons.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "static" / "img" / "icons-src"
OUT = ROOT / "static" / "js" / "core" / "icons.js"

INNER_RE = re.compile(r"<svg[^>]*>(.*)</svg>", re.DOTALL)


def collect() -> dict[str, str]:
    icons: dict[str, str] = {}
    for path in sorted(SRC.glob("*.svg")):
        text = path.read_text(encoding="utf-8")
        match = INNER_RE.search(text)
        if not match:
            print(f"skip (no svg content): {path.name}")
            continue
        inner = match.group(1).strip()
        # normalise whitespace so the generated file stays readable
        inner = re.sub(r">\s+<", "><", inner)
        icons[path.stem] = inner
    return icons


def main() -> None:
    icons = collect()
    payload = json.dumps(icons, ensure_ascii=False, separators=(",", ":"))
    content = f"""/* Auto-generated from Lucide icons (ISC license) by scripts/build_icons.py.
 * Do not edit by hand — re-run the script instead. */

const ICON_PATHS = {payload};

/** Return an inline SVG string for a Lucide icon (themed via currentColor). */
export function icon(name, cls = '') {{
  const inner = ICON_PATHS[name] || ICON_PATHS['circle-help'] || '';
  const classAttr = cls ? ` class="icon ${{cls}}"` : ' class="icon"';
  return `<svg${{classAttr}} viewBox="0 0 24 24" fill="none" stroke="currentColor"
    stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
    aria-hidden="true" focusable="false">${{inner}}</svg>`;
}}

export function hydrateIcons(root = document) {{
  root.querySelectorAll('[data-icon]').forEach((el) => {{
    el.innerHTML = icon(el.dataset.icon, el.dataset.iconClass || '');
  }});
}}

export const ICON_NAMES = Object.keys(ICON_PATHS);
"""
    OUT.write_text(content, encoding="utf-8")
    print(f"wrote {OUT} ({len(icons)} icons)")


if __name__ == "__main__":
    main()
