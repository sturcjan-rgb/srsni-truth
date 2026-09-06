"""
Dočasný diagnostický skript (kolo 9) - budoucí zápasy nemají <tr>
rodiče. Podíváme se přímo na strukturu kolem odkazu (rodiče postupně
nahoru), abychom zjistili, jak jsou budoucí zápasy v HTML rozpisu
skutečně zabalené.
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
shown = 0
for link in soup.find_all("a", href=True):
    m = MATCH_LINK_RE_NEW.match(link["href"].strip())
    if not m or m.group(1) in seen_ids:
        continue
    seen_ids.add(m.group(1))
    shown += 1
    if shown > 1:
        break

    print(f"--- nbl_id={m.group(1)} ---")
    print("link tag:", str(link)[:200])
    node = link
    for level in range(6):
        node = node.parent
        if node is None:
            print(f"úroveň {level+1}: None")
            break
        name = node.name
        classes = node.get("class")
        print(f"úroveň {level+1}: <{name} class={classes}>")
    print()
    print("Kontext (5 úrovní nahoru, celé HTML, zkráceno na 3000 znaků):")
    context = link
    for _ in range(5):
        if context.parent:
            context = context.parent
    print(str(context)[:3000])
