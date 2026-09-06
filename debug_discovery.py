"""
Dočasný diagnostický skript (kolo 10) - moje předchozí hledání
zachytilo odkazy z hlavičky stránky (globální nav), ne z tabulky
rozpisu. Teď hledáme jen uvnitř <main>.
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

main = soup.find("main")
print(f"main nalezeno: {main is not None}")
if main is None:
    exit()

seen_ids = set()
shown = 0
for link in main.find_all("a", href=True):
    m = MATCH_LINK_RE_NEW.match(link["href"].strip())
    if not m or m.group(1) in seen_ids:
        continue
    seen_ids.add(m.group(1))
    shown += 1
    if shown > 3:
        continue

    tr = link.find_parent("tr")
    print(f"--- nbl_id={m.group(1)} ---")
    if tr is None:
        print("(žádný <tr> rodič)")
        print("link tag:", str(link)[:200])
    else:
        cells = tr.find_all(["td", "th"])
        print(f"počet buněk: {len(cells)}")
        for i, cell in enumerate(cells):
            print(f"  [{i}] data-sort={cell.get('data-sort')!r} text={cell.get_text(' ', strip=True)!r}")
    print()

print(f"Celkem unikátních nbl_id uvnitř <main>: {len(seen_ids)}")
