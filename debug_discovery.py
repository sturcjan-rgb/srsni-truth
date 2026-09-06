"""
Dočasný diagnostický skript - spouští se jen přes CI (má přístup k síti),
aby bylo vidět skutečnou strukturu stránky nbl.basketball. Po opravě
discovery.py/sync.py se smaže.
"""

import re

import requests
from bs4 import BeautifulSoup

from discovery import MATCH_LINK_RE, TEAM_URL, USER_AGENT

session = requests.Session()
session.headers["User-Agent"] = USER_AGENT

response = session.get(TEAM_URL, timeout=15)
response.raise_for_status()
html = response.text
soup = BeautifulSoup(html, "html.parser")

print(f"HTML délka: {len(html)} znaků")
print()

print("=== Odkazy, které vypadají jako přepínač sezóny ===")
season_like_re = re.compile(r"20\d{2}\s*/\s*\d{2}|20\d{2}-\d{2}|20\d{2}/20\d{2}")
for link in soup.find_all("a", href=True):
    text = link.get_text(" ", strip=True)
    if season_like_re.search(text):
        print(f"href={link['href']!r} text={text!r}")

print()
print("=== Prvních 5 odkazů na zápas + jejich okolí ===")
count = 0
for link in soup.find_all("a", href=True):
    match = MATCH_LINK_RE.match(link["href"])
    if not match:
        continue
    count += 1
    if count > 5:
        break
    print(f"--- nbl_id={match.group(1)} ---")
    print("link.parent.get_text:", repr(link.parent.get_text(" ", strip=True)) if link.parent else None)
    # o úroveň výš - třeba je datum/tým mimo bezprostředního rodiče
    grandparent = link.parent.parent if link.parent else None
    print("grandparent.get_text:", repr(grandparent.get_text(" ", strip=True)) if grandparent else None)
    print("link.parent HTML (zkráceno na 500 znaků):")
    print(str(link.parent)[:500] if link.parent else None)
    print()

print(f"Celkem nalezeno odkazů na zápas: {count if count <= 5 else 'víc než 5 (viz výše prvních 5)'}")
all_ids = {MATCH_LINK_RE.match(a["href"]).group(1) for a in soup.find_all("a", href=True) if MATCH_LINK_RE.match(a["href"])}
print(f"Celkem unikátních nbl_id na stránce: {len(all_ids)}")

print()
print("=== Odkazy s textem naznačujícím rozpis/výsledky/kalendář ===")
keyword_re = re.compile(r"rozpis|výsledk|zápas|kalend|schedule|program|sez[oó]n", re.IGNORECASE)
seen_hrefs = set()
for link in soup.find_all("a", href=True):
    href = link["href"]
    text = link.get_text(" ", strip=True)
    if keyword_re.search(text) or keyword_re.search(href):
        if href not in seen_hrefs:
            seen_hrefs.add(href)
            print(f"href={href!r} text={text!r}")

print()
print("=== Všechny unikátní vzory odkazů (první segment cesty) ===")
path_prefixes = {}
for link in soup.find_all("a", href=True):
    href = link["href"]
    if href.startswith("/"):
        prefix = "/" + href.strip("/").split("/")[0]
        path_prefixes[prefix] = path_prefixes.get(prefix, 0) + 1
for prefix, cnt in sorted(path_prefixes.items(), key=lambda x: -x[1]):
    print(f"{prefix}: {cnt}x")
