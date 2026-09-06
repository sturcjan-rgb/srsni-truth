"""Dočasný diagnostický skript - ověří, co GitHub Pages skutečně servíruje."""

import requests

r = requests.get("https://sturcjan-rgb.github.io/srsni-truth/static/style.css", timeout=20)
print("status:", r.status_code)
print("cache headers:", {k: v for k, v in r.headers.items() if "cach" in k.lower() or "etag" in k.lower() or "age" in k.lower()})
print()
print("obsahuje 'Anton'?", "Anton" in r.text)
print("obsahuje '--font-display'?", "--font-display" in r.text)
print()
print("prvních 15 řádků:")
print("\n".join(r.text.splitlines()[:15]))

print()
print("=== index.html ===")
r2 = requests.get("https://sturcjan-rgb.github.io/srsni-truth/index.html", timeout=20)
print("status:", r2.status_code)
print("cache headers:", {k: v for k, v in r2.headers.items() if "cach" in k.lower() or "etag" in k.lower() or "age" in k.lower()})
print("odkaz na style.css v HTML:")
for line in r2.text.splitlines():
    if "style.css" in line:
        print(line)
