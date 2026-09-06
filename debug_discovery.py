"""
Dočasný diagnostický skript (kolo 8) - ověří strukturu <tr> pro BUDOUCÍ
zápas (sezóna 2026/27, bez skóre), aby šlo bezpečně parsovat i zápasy,
které se ještě neodehrály.
"""

import re

import requests
from bs4 import BeautifulSoup

from discovery import USER_AGENT

session = requests.Session()
session.headers["User-Agent"] = USER_AGENT

MATCH_LINK_RE_NEW = re.compile(r"^/zapas/(\d+)(?:#.*)?$")

url = "https://nbl.basketball/zapasy?y=2026&c=421&p1=0&k=0&d_od=&d_do="
r = session.get(url, timeout=20)
r.raise_for_status()
soup = BeautifulSoup(r.text, "html.parser")

seen_ids = set()
rows_shown = 0
for link in soup.find_all("a", href=True):
    m = MATCH_LINK_RE_NEW.match(link["href"].strip())
    if not m or m.group(1) in seen_ids:
        continue
    seen_ids.add(m.group(1))
    rows_shown += 1
    if rows_shown > 2:
        break

    tr = link.find_parent("tr")
    print(f"--- nbl_id={m.group(1)} ---")
    if tr is None:
        print("(žádný <tr> rodič)")
        continue
    cells = tr.find_all(["td", "th"])
    print(f"počet buněk: {len(cells)}")
    for i, cell in enumerate(cells):
        print(f"  [{i}] data-sort={cell.get('data-sort')!r} text={cell.get_text(' ', strip=True)!r}")
    print("tr outer HTML (zkráceno na 2000 znaků):")
    print(str(tr)[:2000])
    print()
