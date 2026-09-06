"""
Dočasný diagnostický skript (kolo 3) - ověří skutečnou URL rozpisu
(/tym/srsni-photomate-pisek/zapasy) a stránku pro přepínání sezóny
(/tym/srsni-photomate-pisek/sezona), které se našly v kole 2.
"""

import re

import requests
from bs4 import BeautifulSoup

from discovery import MATCH_LINK_RE, TEAM_URL, USER_AGENT

session = requests.Session()
session.headers["User-Agent"] = USER_AGENT


def fetch(url):
    r = session.get(url, timeout=15)
    r.raise_for_status()
    return r.text


print("=" * 20, "SCHEDULE URL", "=" * 20)
schedule_url = f"{TEAM_URL}/zapasy?d_od=&d_do=&k=0"
html = fetch(schedule_url)
soup = BeautifulSoup(html, "html.parser")
print(f"URL: {schedule_url}")
print(f"HTML délka: {len(html)}")

all_ids = {}
for link in soup.find_all("a", href=True):
    m = MATCH_LINK_RE.match(link["href"])
    if m:
        all_ids.setdefault(m.group(1), link)

print(f"Celkem unikátních nbl_id: {len(all_ids)}")
print()
print("Prvních 5 zápasů (nbl_id + text rodiče/prarodiče):")
for i, (nbl_id, link) in enumerate(all_ids.items()):
    if i >= 5:
        break
    parent_text = link.parent.get_text(" ", strip=True) if link.parent else None
    grandparent = link.parent.parent if link.parent else None
    grandparent_text = grandparent.get_text(" ", strip=True) if grandparent else None
    print(f"--- {nbl_id} ---")
    print("parent:", repr(parent_text))
    print("grandparent:", repr(grandparent_text))

print()
print("=" * 20, "SEZONA URL", "=" * 20)
sezona_url = f"{TEAM_URL}/sezona"
try:
    html2 = fetch(sezona_url)
    soup2 = BeautifulSoup(html2, "html.parser")
    print(f"URL: {sezona_url}")
    print(f"HTML délka: {len(html2)}")
    season_like_re = re.compile(r"20\d{2}\s*/\s*\d{2}|20\d{2}-\d{2}")
    print("Odkazy vypadající jako sezóny:")
    for link in soup2.find_all("a", href=True):
        text = link.get_text(" ", strip=True)
        if season_like_re.search(text):
            print(f"href={link['href']!r} text={text!r}")
except requests.RequestException as e:
    print(f"chyba: {e}")
