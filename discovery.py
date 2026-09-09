"""
Discovery: najde všechny zápasy Sršňů Photomate Písek v dané sezóně.

Zdroj dat: rozpis zápasů celé ligy na https://nbl.basketball/zapasy,
staticky vykreslený jako tabulka, s filtrem podle týmu a sezóny v query
parametrech GET formuláře na téhle stránce:

- "c"  = ID týmu (Sršni Photomate Písek má ID 421 - zjištěno z <select
         name="c"> na stránce, viz její možnosti)
- "y"  = počáteční rok sezóny (2025 pro sezónu "2025/26", 2026 pro
         "2026/27", ...)
- "p1" = fáze sezóny (0 = všechny - základní část i play-off)
- "k"  = kolo (0 = všechna)

Tahle stránka obsahuje i BUDOUCÍ (ještě neodehrané) zápasy - jen bez
skóre. U odehraných zápasů je skóre uvnitř odkazu na detail zápasu
(/zapas/<id>#tab-pane-one), u budoucích je odkaz na náhled
(/zapas/<id>#tab-pane-two). Datum+čas výkopu je navíc v atributu
data-sort buňky s datem, ve formátu "YYYY-MM-DD-HH-MM" (lokální čas
Evropa/Praha) - mnohem spolehlivější než parsovat zobrazený text.

Poznámka: dřívější verze tohohle modulu cílila na
https://nbl.basketball/tym/srsni-photomate-pisek, což se ukázalo jako
omyl - ta stránka je jen malý "poslední výsledek + příští zápas" widget,
ne celý rozpis. Skutečnou strukturu (URL s parametry, sloupce tabulky)
se podařilo zjistit až empiricky přes diagnostické běhy v GitHub
Actions (síť ve vývojové sandboxi byla k nbl.basketball zablokovaná
organizační politikou).
"""

from __future__ import annotations

import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

import requests
from bs4 import BeautifulSoup

SCHEDULE_URL = "https://nbl.basketball/zapasy"
TEAM_ID = 421  # Sršni Photomate Písek

# Slušné chování vůči cizímu webu: představíme se a mezi requesty počkáme.
USER_AGENT = "srsni-data/0.1 (+kontakt: klub Srsni Photomate Pisek; osobni projekt pro vlastni statistiky)"
REQUEST_DELAY_SECONDS = 0.8

# Odkaz na detail zápasu má tvar /zapas/<id>, případně s fragmentem
# (#tab-pane-one u odehraných, #tab-pane-two u budoucích zápasů).
MATCH_LINK_RE = re.compile(r"^/zapas/(\d+)(?:#.*)?$")

# Přímý odkaz na FIBA LiveStats webcast, pokud ho tabulka už obsahuje.
FIBA_WEBCAST_RE = re.compile(r"https://www\.fibalivestats\.com/webcast/[^/\s\"']+/(\d+)/?")

# Formát atributu data-sort na buňce s datem: "2025-10-04-18-00".
DATE_SORT_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})-(\d{2})-(\d{2})$")

PRAGUE_TZ = ZoneInfo("Europe/Prague")


@dataclass
class DiscoveredMatch:
    """Jeden zápas nalezený v rozpisu."""

    nbl_id: int
    url: str
    date_utc: str | None
    home_team: str | None
    away_team: str | None
    fiba_id: int | None  # vyplněné, pokud tabulka už obsahuje odkaz na FIBA LiveStats


def _season_start_year(season: str) -> int:
    """Z řetězce jako '2025/26' vytáhne počáteční rok sezóny (2025)."""
    return int(season.split("/")[0])


def _parse_date_cell(cell) -> str | None:
    """Vytáhne datum+čas z atributu data-sort (lokální čas -> UTC ISO string)."""
    raw = cell.get("data-sort")
    if not raw:
        return None
    match = DATE_SORT_RE.match(raw)
    if not match:
        return None
    year, month, day, hour, minute = (int(x) for x in match.groups())
    try:
        local_dt = datetime(year, month, day, hour, minute, tzinfo=PRAGUE_TZ)
    except ValueError:
        return None
    return local_dt.astimezone(timezone.utc).isoformat()


def _parse_teams_cell(cell) -> tuple[str | None, str | None]:
    """
    Vytáhne domácí a hostující tým ze sloupce "domácí / hosté".

    V buňce jsou dvě "listové" <div> (bez vlastních vnořených <div>) v
    pořadí domácí, hosté - obalující <div> by při get_text() vrátil
    oba texty spojené dohromady, proto filtrujeme jen ty bez potomků.
    """
    leaf_divs = [d for d in cell.find_all("div") if not d.find("div")]
    texts = [d.get_text(strip=True) for d in leaf_divs if d.get_text(strip=True)]
    if len(texts) >= 2:
        return texts[0], texts[1]
    return None, None


def _extract_fiba_id(row) -> int | None:
    """Pokud řádek zápasu obsahuje přímý odkaz na FIBA LiveStats, vytáhne fiba_id."""
    for link in row.find_all("a", href=True):
        match = FIBA_WEBCAST_RE.search(link["href"])
        if match:
            return int(match.group(1))
    return None


def _get(session: requests.Session, url: str, params: dict) -> str:
    """Stáhne stránku a vrátí HTML. Mezi voláními počká, ať web nezatěžujeme."""
    response = session.get(url, params=params, timeout=15)
    response.raise_for_status()
    time.sleep(REQUEST_DELAY_SECONDS)
    return response.text


def discover_matches(season: str) -> list[DiscoveredMatch]:
    """
    Vrátí seznam zápasů Sršňů pro danou sezónu, např. "2025/26".

    Zahrnuje i budoucí (ještě neodehrané) zápasy - tabulka na
    nbl.basketball je obsahuje stejně jako odehrané, jen bez skóre.
    """
    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    params = {
        "y": _season_start_year(season),
        "c": TEAM_ID,
        "p1": 0,  # všechny fáze sezóny (základní část i play-off)
        "k": 0,  # všechna kola
        "d_od": "",
        "d_do": "",
    }
    html = _get(session, SCHEDULE_URL, params)
    # lxml (ne stdlib "html.parser") - u některých řádků rozpisu je
    # HTML mírně poškozené (chybí <tr> obal) a "html.parser" v takovém
    # případě celý řádek ztratí (žádný <tr> předek -> zápas se vůbec
    # nenačte). lxml se s tím umí vyrovnat stejně shovívavě jako
    # prohlížeč a řádek správně zrekonstruuje.
    soup = BeautifulSoup(html, "lxml")

    # Hledáme jen uvnitř <main> - v hlavičce stránky je vlastní "další
    # zápas" widget s odkazem na /zapas/<id>, který by jinak matchnul
    # taky, ale nemá žádná další data k vytažení (viz find_parent("tr")
    # níže, který takové odkazy stejně přeskočí).
    main = soup.find("main") or soup

    matches: dict[int, DiscoveredMatch] = {}
    for link in main.find_all("a", href=True):
        match = MATCH_LINK_RE.match(link["href"].strip())
        if not match:
            continue
        nbl_id = int(match.group(1))
        if nbl_id in matches:
            continue

        row = link.find_parent("tr")
        if row is None:
            # Odkaz mimo tabulku (např. widget nad rozpisem) - nemá
            # sloupce k vytažení, přeskočíme.
            continue

        cells = row.find_all(["td", "th"])
        date_utc = _parse_date_cell(cells[2]) if len(cells) > 2 else None
        home_team, away_team = _parse_teams_cell(cells[3]) if len(cells) > 3 else (None, None)
        fiba_id = _extract_fiba_id(row)

        matches[nbl_id] = DiscoveredMatch(
            nbl_id=nbl_id,
            url=f"https://nbl.basketball/zapas/{nbl_id}",
            date_utc=date_utc,
            home_team=home_team,
            away_team=away_team,
            fiba_id=fiba_id,
        )

    return list(matches.values())


if __name__ == "__main__":
    import sys

    season_arg = sys.argv[1] if len(sys.argv) > 1 else "2025/26"
    for m in discover_matches(season_arg):
        print(m)
