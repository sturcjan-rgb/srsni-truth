import requests
from bs4 import BeautifulSoup

from discovery import SCHEDULE_URL, TEAM_ID, USER_AGENT, MATCH_LINK_RE

session = requests.Session()
session.headers["User-Agent"] = USER_AGENT

params = {"y": 2026, "c": TEAM_ID, "p1": 0, "k": 0, "d_od": "", "d_do": ""}
resp = session.get(SCHEDULE_URL, params=params, timeout=15)
print("status", resp.status_code, "final url", resp.url)
html = resp.text
print("html length", len(html))
print("contains SLUNETA:", "SLUNETA" in html)
print("contains GAPA:", "GAPA" in html)

soup = BeautifulSoup(html, "html.parser")
main = soup.find("main") or soup

all_links = main.find_all("a", href=True)
match_links = [l for l in all_links if MATCH_LINK_RE.match(l["href"].strip())]
print("total <a> in main:", len(all_links))
print("match-shaped links:", len(match_links))
ids_seen = []
for link in match_links:
    m = MATCH_LINK_RE.match(link["href"].strip())
    ids_seen.append(int(m.group(1)))
print("distinct nbl_ids found:", sorted(set(ids_seen)))

# Find the row containing SLUNETA and dump its raw HTML
sluneta_idx = html.find("SLUNETA")
if sluneta_idx != -1:
    print()
    print("=== context around SLUNETA in raw html ===")
    print(html[max(0, sluneta_idx - 1500):sluneta_idx + 500])
