import requests
from bs4 import BeautifulSoup

from discovery import SCHEDULE_URL, TEAM_ID, USER_AGENT, MATCH_LINK_RE

session = requests.Session()
session.headers["User-Agent"] = USER_AGENT
params = {"y": 2026, "c": TEAM_ID, "p1": 0, "k": 0, "d_od": "", "d_do": ""}
html = session.get(SCHEDULE_URL, params=params, timeout=15).text

for parser_name in ("html.parser", "html5lib", "lxml"):
    print(f"=== parser: {parser_name} ===")
    try:
        soup = BeautifulSoup(html, parser_name)
    except Exception as e:
        print("  failed to parse:", e)
        continue
    main = soup.find("main") or soup
    for target_id in ("544546", "544552"):
        found = False
        for link in main.find_all("a", href=True):
            m = MATCH_LINK_RE.match(link["href"].strip())
            if not m or m.group(1) != target_id:
                continue
            found = True
            row = link.find_parent("tr")
            print(f"  {target_id}: has <tr> parent = {row is not None}")
        if not found:
            print(f"  {target_id}: no link found at all")
