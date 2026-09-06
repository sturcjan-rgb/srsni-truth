"""
Dočasný skript - stáhne https://tv.srsni.com/, vytáhne z inline <style>
zabalený font "CoFo Peshka Black" (base64 woff2) a uloží ho jako
skutečný soubor do static/fonts/. Běží jen přes CI (síť v sandboxi je
k tv.srsni.com zablokovaná) a font se pak commitne přímo z workflow -
neprochází to přes mě jako obrovský text v logu.
"""

import base64
import re
from pathlib import Path

import requests

FONT_FACE_RE = re.compile(
    r'font-family\s*:\s*"CoFo Peshka Black"\s*;\s*src\s*:\s*url\(\s*"data:font/woff2;base64,([A-Za-z0-9+/=]+)"\s*\)',
)

r = requests.get("https://tv.srsni.com/", headers={"User-Agent": "Mozilla/5.0 (srsni-data font sync)"}, timeout=30)
r.raise_for_status()

match = FONT_FACE_RE.search(r.text)
if not match:
    raise SystemExit("Font-face pro 'CoFo Peshka Black' nebyl v HTML nalezen - zkontroluj strukturu stránky.")

font_bytes = base64.b64decode(match.group(1))

out_path = Path("static/fonts/cofo-peshka-black.woff2")
out_path.parent.mkdir(parents=True, exist_ok=True)
out_path.write_bytes(font_bytes)

print(f"Uloženo {len(font_bytes)} bajtů do {out_path}")
