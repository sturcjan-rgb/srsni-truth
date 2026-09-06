"""
Dočasný diagnostický skript (kolo 4) - /zapasy je root-relative (404 pod
/tym/.../zapasy). Zkusíme: /tym/.../statistiky (má taky záložku
"Zápasy"), /tym/.../sezona, a kořenové /zapasy s parametrem týmu.
"""

import requests
from bs4 import BeautifulSoup

from discovery import MATCH_LINK_RE, TEAM_URL, USER_AGENT

session = requests.Session()
session.headers["User-Agent"] = USER_AGENT


def try_url(label, url):
    print("=" * 20, label, "=" * 20)
    print(f"URL: {url}")
    try:
        r = session.get(url, timeout=15)
        print(f"status: {r.status_code}")
        if r.status_code != 200:
            print(r.text[:300])
            print()
            return None
        html = r.text
    except requests.RequestException as e:
        print(f"chyba: {e}")
        print()
        return None

    soup = BeautifulSoup(html, "html.parser")
    print(f"HTML délka: {len(html)}")
    ids = {}
    for link in soup.find_all("a", href=True):
        m = MATCH_LINK_RE.match(link["href"])
        if m:
            ids.setdefault(m.group(1), link)
    print(f"Unikátních nbl_id: {len(ids)}")
    for i, (nbl_id, link) in enumerate(ids.items()):
        if i >= 3:
            break
        parent_text = link.parent.get_text(" ", strip=True) if link.parent else None
        print(f"  {nbl_id}: {parent_text!r}")
    print()
    return soup


try_url("STATISTIKY", f"{TEAM_URL}/statistiky")
try_url("SEZONA", f"{TEAM_URL}/sezona")
try_url("ROOT ZAPASY (bez filtru)", "https://nbl.basketball/zapasy")
try_url("ROOT ZAPASY (s d_od/d_do/k)", "https://nbl.basketball/zapasy?d_od=&d_do=&k=0")
