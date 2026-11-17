"""
sync.py - orchestrátor, který dá dohromady discovery, resolve a stažení
statistik do jedné databáze.

Postup pro danou sezónu:

1. discovery.discover_matches(season) - najde zápasy Sršňů (včetně
   budoucích) a uloží je (nebo aktualizuje) do tabulky matches. Datum,
   domácí/hosté tým a případně i fiba_id (pokud ho už rozpis obsahuje)
   se berou přímo z tabulky rozpisu - viz discovery.py.
2. Pro zápasy, které ještě fiba_id nemají (rozpis ho ještě neobsahoval),
   zkusí resolve.get_fiba_id jako záložní krok - pokud zápas ještě nemá
   přiřazený FIBA feed, v klidu to přeskočí.
3. Pro zápasy, které fiba_id mají, a nemají ještě dnešní snapshot (nebo
   nejsou "finished"), stáhne https://fibalivestats.dcd.shared.geniussports.com/data/<fiba_id>/data.json,
   uloží ho jako nový snapshot a podle stats.is_match_finished()
   aktualizuje status zápasu na finished/live/upcoming.
"""

from __future__ import annotations

import json
import sys
import time
from datetime import date, datetime, timezone
from pathlib import Path

import requests

import db
import resolve
import stats
from discovery import USER_AGENT, discover_matches

FIBA_DATA_URL_TEMPLATE = "https://fibalivestats.dcd.shared.geniussports.com/data/{fiba_id}/data.json"

REQUEST_DELAY_SECONDS = 0.8

# Ručně zadaná FIBA ID ({"<nbl_id>": <fiba_id>}) - pojistka pro případ, kdy
# nbl.basketball FIBA odkaz neukáže nebo je nedostupný (od 11/2026 vrací
# runnerům GitHub Actions HTTP 403).
FIBA_OVERRIDES_PATH = Path(__file__).with_name("fiba_overrides.json")


def load_fiba_overrides(path: Path = FIBA_OVERRIDES_PATH) -> dict[int, int]:
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    return {int(k): int(v) for k, v in data.items() if v}


def current_season_guess(today: date | None = None) -> str:
    """
    Odhadne aktuální sezónu podle data - NBL sezóna začíná na podzim
    (kolem září) a končí následující jaro. Použije se jako výchozí
    hodnota, když volající explicitně nezadá sezónu.
    """
    today = today or datetime.now(timezone.utc).date()
    start_year = today.year if today.month >= 7 else today.year - 1
    return f"{start_year}/{str(start_year + 1)[-2:]}"


def fetch_fiba_data(fiba_id: int, session: requests.Session) -> dict:
    """Stáhne aktuální data.json pro daný fiba_id."""
    url = FIBA_DATA_URL_TEMPLATE.format(fiba_id=fiba_id)
    response = session.get(url, timeout=15)
    response.raise_for_status()
    return response.json()


def _decide_status(raw_json: dict, date_utc: str | None) -> str:
    """
    Rozhodne stav zápasu podle pravidla ze zadání: perioda 4 + čas 00:00
    (a bez OT) = finished; jinak live/upcoming podle naplánovaného termínu.
    """
    if stats.is_match_finished(raw_json):
        return "finished"

    if date_utc is None:
        # Bez známého termínu radši předpokládáme, že se hraje (máme přece
        # čerstvá data z FIBA feedu, takže zápas evidentně existuje).
        return "live"

    kickoff = datetime.fromisoformat(date_utc)
    now = datetime.now(timezone.utc)
    return "upcoming" if kickoff > now else "live"


def sync_season(season: str | None = None, db_path=db.DB_PATH) -> dict:
    """
    Provede jeden kompletní synchronizační běh pro danou sezónu.

    season: např. "2025/26". Když se vynechá, odhadne se aktuální
    sezóna podle dnešního data (current_season_guess).

    Vrací malé shrnutí (kolik zápasů objeveno/resolvováno/staženo), ať má
    volající (CLI nebo MCP nástroj sync_schedule) co ukázat uživateli.
    """
    season = season or current_season_guess()

    session = requests.Session()
    session.headers["User-Agent"] = USER_AGENT

    summary = {"discovered": 0, "resolved": 0, "snapshots_saved": 0}

    with db.connect(db_path) as conn:
        try:
            discovered = discover_matches(season)
        except requests.RequestException as exc:
            # Nedostupný rozpis nesmí shodit celý sync - zápasy už v DB jsou
            # a FIBA data (krok 3) se dají stáhnout i bez nbl.basketball.
            print(f"WARN rozpis se nepodařilo stáhnout ({exc}) - pokračuji se zápasy z DB", file=sys.stderr)
            discovered = []
        summary["discovered"] = len(discovered)

        for item in discovered:
            db.upsert_match(
                conn,
                item.nbl_id,
                season=season,
                date_utc=item.date_utc,
                home_team=item.home_team,
                away_team=item.away_team,
                fiba_id=item.fiba_id,
            )

        for nbl_id, fiba_id in load_fiba_overrides().items():
            match = db.get_match(conn, nbl_id)
            if match is not None and match.season == season and match.fiba_id != fiba_id:
                db.upsert_match(conn, nbl_id, fiba_id=fiba_id)
                summary["resolved"] += 1

        matches = db.list_matches(conn, season=season)

        # Krok 2: dohledat fiba_id u zápasů, které ho ještě nemají
        # (rozpis ho ještě neobsahoval - typicky u zápasů dál v budoucnu).
        for match in matches:
            if match.fiba_id is not None:
                continue
            try:
                fiba_id = resolve.get_fiba_id(match.nbl_id, session)
            except requests.RequestException:
                continue
            time.sleep(REQUEST_DELAY_SECONDS)
            if fiba_id is not None:
                db.upsert_match(conn, match.nbl_id, fiba_id=fiba_id)
                summary["resolved"] += 1

        # Krok 3: stáhnout aktuální data.json tam, kde dává smysl.
        for match in db.list_matches(conn, season=season):
            if match.fiba_id is None:
                continue
            if match.status == "finished" and db.has_any_snapshot(conn, match.nbl_id):
                # Skončený zápas se už nezmění - jeden snapshot navždy stačí.
                # (Dřív se kontrolovalo jen "má snapshot z dneška", takže se
                # stejná data ukládala znovu každý den, donekonečna.)
                continue

            try:
                raw_json = fetch_fiba_data(match.fiba_id, session)
            except requests.RequestException:
                continue
            time.sleep(REQUEST_DELAY_SECONDS)

            db.add_snapshot(conn, match.nbl_id, raw_json, clock=raw_json.get("clock"), period=raw_json.get("period"))
            new_status = _decide_status(raw_json, match.date_utc)
            db.upsert_match(conn, match.nbl_id, status=new_status)
            db.mark_synced(conn, match.nbl_id)
            summary["snapshots_saved"] += 1

    db.compact(db_path)
    return summary


if __name__ == "__main__":
    import sys

    season_arg = sys.argv[1] if len(sys.argv) > 1 else None
    result = sync_season(season_arg)
    print(f"Sezóna: {season_arg or current_season_guess() + ' (odhad)'}")
    print(f"Objeveno zápasů: {result['discovered']}")
    print(f"Dohledáno nových fiba_id: {result['resolved']}")
    print(f"Uloženo nových snapshotů: {result['snapshots_saved']}")
