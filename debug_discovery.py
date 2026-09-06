"""
Dočasný diagnostický skript (kolo 6) - ověří finální URL rozpisu:
/zapasy?y=<rok>&c=421&p1=0&k=0&d_od=&d_do=
kde y=rok počátku sezóny (2025 pro 2025/26), c=421 je Sršni Photomate
Písek, a odkazy na zápas mají tvar /zapas/<id>#tab-pane-two.
"""

import re

import requests
from bs4 import BeautifulSoup

from discovery import USER_AGENT

session = requests.Session()
session.headers["User-Agent"] = USER_AGENT

MATCH_LINK_RE_NEW = re.compile(r"^/zapas/(\d+)(?:#.*)?$")


def check_season(year):
    url = f"https://nbl.basketball/zapasy?y={year}&c=421&p1=0&k=0&d_od=&d_do="
    r = session.get(url, timeout=20)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    ids = {}
    for link in soup.find_all("a", href=True):
        m = MATCH_LINK_RE_NEW.match(link["href"].strip())
        if m:
            ids.setdefault(m.group(1), link)

    print(f"=== rok={year} (sezóna {year}/{str(int(year) + 1)[-2:]}) ===")
    print(f"URL: {url}")
    print(f"Unikátních nbl_id: {len(ids)}")
    for i, (nbl_id, link) in enumerate(ids.items()):
        if i >= 3:
            break
        row = link
        for _ in range(4):
            if row.parent:
                row = row.parent
        print(f"  {nbl_id}: řádek text = {row.get_text(' ', strip=True)!r}")
        print(f"       přímý parent text = {link.parent.get_text(' ', strip=True)!r}" if link.parent else "")
    print()
    return ids


for year in (2025, 2026):
    check_season(year)
