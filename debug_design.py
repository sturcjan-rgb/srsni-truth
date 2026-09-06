"""
Dočasný diagnostický skript - stáhne https://tv.srsni.com/ (síť v sandboxi
je k téhle doméně taky zablokovaná) a vytáhne barvy/fonty pro design
portálu. Po použití se smaže.
"""

import re

import requests

HEADERS = {"User-Agent": "Mozilla/5.0 (srsni-data design research)"}

r = requests.get("https://tv.srsni.com/", headers=HEADERS, timeout=20)
r.raise_for_status()
html = r.text
print(f"HTML délka: {len(html)}")

print()
print("=== <title>, meta theme-color, favicon, OG tags ===")
for pattern in [
    r"<title>.*?</title>",
    r'<meta[^>]*theme-color[^>]*>',
    r'<link[^>]*icon[^>]*>',
    r'<meta[^>]*og:image[^>]*>',
    r'<meta[^>]*og:site_name[^>]*>',
]:
    for m in re.findall(pattern, html, re.IGNORECASE):
        print(m)

print()
print("=== inline <style> bloky (prvnich 3000 znaku kazdeho) ===")
for i, style in enumerate(re.findall(r"<style[^>]*>(.*?)</style>", html, re.DOTALL)):
    print(f"--- style block {i} ---")
    print(style[:3000])
    print()

print()
print("=== odkazy na externi CSS soubory ===")
css_links = re.findall(r'<link[^>]*rel=["\']stylesheet["\'][^>]*href=["\']([^"\']+)["\']', html)
css_links += re.findall(r'<link[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\']stylesheet["\']', html)
css_links = list(dict.fromkeys(css_links))
print(css_links)

print()
print("=== stahovani externich CSS a hledani barev/fontu ===")
color_re = re.compile(r"#[0-9a-fA-F]{3,8}\b|rgba?\([^)]+\)")
font_re = re.compile(r"font-family\s*:\s*[^;]+;")

for href in css_links[:6]:
    url = href if href.startswith("http") else f"https://tv.srsni.com{href if href.startswith('/') else '/' + href}"
    try:
        cr = requests.get(url, headers=HEADERS, timeout=20)
        cr.raise_for_status()
        css = cr.text
    except requests.RequestException as e:
        print(f"chyba pri stahovani {url}: {e}")
        continue
    print(f"--- {url} ({len(css)} znaku) ---")
    fonts = sorted(set(font_re.findall(css)))
    print("fonty:", fonts[:20])
    colors = sorted(set(color_re.findall(css)))
    print(f"pocet unikatnich barev: {len(colors)}")
    print("prvnich 40 barev:", colors[:40])
    print()

print()
print("=== hledani google fonts / font odkazu v HTML ===")
for m in re.findall(r'<link[^>]*fonts\.googleapis[^>]*>', html):
    print(m)
for m in re.findall(r'@font-face\s*\{[^}]+\}', html):
    print(m[:300])
