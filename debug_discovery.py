import requests
from bs4 import BeautifulSoup

from discovery import SCHEDULE_URL, TEAM_ID, USER_AGENT, MATCH_LINK_RE

session = requests.Session()
session.headers["User-Agent"] = USER_AGENT
params = {"y": 2026, "c": TEAM_ID, "p1": 0, "k": 0, "d_od": "", "d_do": ""}
html = session.get(SCHEDULE_URL, params=params, timeout=15).text

soup = BeautifulSoup(html, "html.parser")
main = soup.find("main") or soup

for target_id in ("544546", "544552", "544558"):
    print(f"=== target {target_id} ===")
    found_any = False
    for link in main.find_all("a", href=True):
        m = MATCH_LINK_RE.match(link["href"].strip())
        if not m or m.group(1) != target_id:
            continue
        found_any = True
        row = link.find_parent("tr")
        print("  href:", link["href"].strip())
        print("  has <tr> parent:", row is not None)
        # walk up a few ancestors to see the structure
        ancestors = []
        node = link
        for _ in range(6):
            node = node.parent
            if node is None:
                break
            ancestors.append(node.name)
        print("  ancestor chain:", ancestors)
    if not found_any:
        print("  (no matching <a> found at all)")
