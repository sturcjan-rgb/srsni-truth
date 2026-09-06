"""
Dočasný diagnostický skript (kolo 7) - najde <tr> řádek pro každý
zápas a zmapuje sloupce (round, číslo, datum, den, čas, domácí, hosté,
skóre, čtvrtiny, fáze, odkazy).
"""

import re

import requests
from bs4 import BeautifulSoup

from discovery import USER_AGENT

session = requests.Session()
session.headers["User-Agent"] = USER_AGENT

MATCH_LINK_RE_NEW = re.compile(r"^/zapas/(\d+)(?:#.*)?$")

url = "https://nbl.basketball/zapasy?y=2025&c=421&p1=0&k=0&d_od=&d_do="
r = session.get(url, timeout=20)
r.raise_for_status()
soup = BeautifulSoup(r.text, "html.parser")

print("=== Hlavička tabulky (thead), pokud existuje ===")
thead = soup.find("thead")
print(str(thead)[:1000] if thead else "žádná <thead>")
print()

seen_ids = set()
rows_shown = 0
for link in soup.find_all("a", href=True):
    m = MATCH_LINK_RE_NEW.match(link["href"].strip())
    if not m or m.group(1) in seen_ids:
        continue
    seen_ids.add(m.group(1))
    rows_shown += 1
    if rows_shown > 3:
        break

    tr = link.find_parent("tr")
    print(f"--- nbl_id={m.group(1)} ---")
    if tr is None:
        print("(žádný <tr> rodič)")
        # zkusit najít nejbližší menší kontejner
        print("link outer HTML:", str(link)[:300])
        continue
    cells = tr.find_all(["td", "th"])
    print(f"počet buněk v <tr>: {len(cells)}")
    for i, cell in enumerate(cells):
        print(f"  [{i}] {cell.get_text(' ', strip=True)!r}")
    print("tr outer HTML (zkráceno na 1500 znaků):")
    print(str(tr)[:1500])
    print()
