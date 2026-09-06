"""
Dočasný diagnostický skript (kolo 5) - /zapasy?d_od=&d_do=&k=0 vrací 701KB
ale 0 shod na přísný regex ^/zapas/(\\d+)$. Podíváme se na skutečný formát
hrefs a hledáme filtr podle týmu (select/option/input).
"""

import re

import requests
from bs4 import BeautifulSoup

from discovery import USER_AGENT

session = requests.Session()
session.headers["User-Agent"] = USER_AGENT

url = "https://nbl.basketball/zapasy?d_od=&d_do=&k=0"
r = session.get(url, timeout=20)
r.raise_for_status()
html = r.text
soup = BeautifulSoup(html, "html.parser")

print(f"HTML délka: {len(html)}")
print()

print("=== Všechny hrefy obsahující 'zapas' (prvních 10 unikátních vzorů) ===")
seen = set()
count = 0
for link in soup.find_all("a", href=True):
    href = link["href"]
    if "zapas" in href.lower():
        # normalizovat číslo pryč, ať vidíme vzor
        pattern = re.sub(r"\d+", "N", href)
        if pattern not in seen:
            seen.add(pattern)
            count += 1
            print(f"vzor={pattern!r} příklad={href!r}")
        if count >= 10:
            break

print()
print("=== Hledání 'Srsni' / 'Sršni' v HTML ===")
srsni_count = html.lower().count("sršni") + html.lower().count("srsni")
print(f"počet výskytů 'sršni'/'srsni' (case-insensitive): {srsni_count}")

print()
print("=== Formulářové prvky (select/input) - možný filtr týmu ===")
for form in soup.find_all("form"):
    print("FORM action=", form.get("action"), "method=", form.get("method"))
    for field in form.find_all(["select", "input"]):
        name = field.get("name")
        if name:
            print(f"  {field.name} name={name!r}")
            if field.name == "select":
                for opt in field.find_all("option")[:5]:
                    print(f"    option value={opt.get('value')!r} text={opt.get_text(strip=True)!r}")

print()
print("=== Odkaz na první nalezený tým Sršni v HTML (kontext) ===")
idx = html.lower().find("sršni")
if idx == -1:
    idx = html.lower().find("srsni")
if idx != -1:
    print(html[max(0, idx - 300):idx + 300])
