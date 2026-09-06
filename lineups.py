"""
lineups.py - "hluboké" statistiky z play-by-play (pbp) dat FIBA LiveStats:

- které kombinace hráčů (dvojice/trojice/pětky) byly spolu na hřišti,
  když tým dal nejvíc bodů (klasická "lineup" analýza z basketbalové
  analytiky - ne prostý součet bodů jednotlivců, ale kolik bodů tým
  skutečně nastřílel, zatímco tahle konkrétní parta hráčů hrála spolu),
- které dvojice hráčů si nejvíc nahrály na koš (asistence).

Vstupem je vždy celý stažený data.json (nebo snapshot z DB) - stejně
jako u stats.py. Bez síťové závislosti, čisté funkce.

Jak se to počítá (lineups):
1. Najdeme "on-court" pětku Sršňů na začátku zápasu podle pl.starter.
2. Projdeme pbp chronologicky (pole je v datech seřazené OD KONCE
   zápasu, proto se řadí podle actionNumber vzestupně).
3. Na každou substituci (actionType="substitution") aktualizujeme, kdo
   je na hřišti (subType "in"/"out").
4. Na každý proměněný koš (2pt/3pt/freethrow se success=1) tady a teď
   hrající pětky přičteme body ke všem jejím dvojicím, trojicím i k ní
   samotné - tak vznikne "kolik bodů dal tým, když spolu hráli tihle
   lidi".

Jak se to počítá (asistence):
- Událost actionType="assist" odkazuje přes previousAction na
  actionNumber předchozí (proměněné) střely - najdeme, kdo tu střelu
  dal, a spárujeme (nahrávač, střelec).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from itertools import combinations

POINTS_BY_ACTION_TYPE = {"2pt": 2, "3pt": 3, "freethrow": 1}


def find_team_number(raw_json: dict, name_substring: str) -> str | None:
    """Najde klíč týmu v tm podle části jména (case-insensitive)."""
    needle = name_substring.lower()
    for tno, team in raw_json.get("tm", {}).items():
        if needle in team.get("name", "").lower():
            return tno
    return None


def player_names(raw_json: dict, tno: str) -> dict[str, str]:
    """Vrátí mapu player_id -> celé jméno pro daný tým."""
    team = raw_json.get("tm", {}).get(tno, {})
    return {
        pid: f"{p.get('firstName', '')} {p.get('familyName', '')}".strip()
        for pid, p in team.get("pl", {}).items()
    }


@dataclass
class LineupStats:
    """
    Výsledek rozboru pbp pro jeden tým v jednom zápase/snapshotu.

    Kombinace i asistenční dvojice jsou klíčované JMÉNY hráčů, ne jejich
    "pno"/player_id z JSONu - to číslo je totiž stabilní jen v rámci
    jednoho zápasu (FIBA LiveStats ho každému zápasu přiděluje znovu),
    takže při součtu přes víc zápasů by stejné číslo klidně mohlo
    patřit dvěma různým lidem. Jméno je jediná spolehlivá spojnice mezi
    zápasy, kterou máme.
    """

    tno: str
    combo_points: dict[tuple[str, ...], int] = field(default_factory=dict)
    assist_counts: dict[tuple[str, str], int] = field(default_factory=dict)
    assist_points: dict[tuple[str, str], int] = field(default_factory=dict)


def analyze_pbp(raw_json: dict, team_name_substring: str = "sršni") -> LineupStats | None:
    """
    Projde play-by-play jednoho zápasu a spočítá lineup kombinace i
    asistenční dvojice pro tým, jehož jméno obsahuje team_name_substring.

    Vrací None, pokud zápas nemá pbp data (např. ještě neproběhl) nebo
    se hledaný tým nenajde.
    """
    tno = find_team_number(raw_json, team_name_substring)
    if tno is None:
        return None

    pbp = raw_json.get("pbp")
    if not pbp:
        return None

    team = raw_json["tm"][tno]
    on_court = {pid for pid, p in team.get("pl", {}).items() if p.get("starter")}

    events = sorted(pbp, key=lambda e: e.get("actionNumber", 0))
    events_by_number = {e["actionNumber"]: e for e in events if "actionNumber" in e}

    combo_points: dict[tuple[str, ...], int] = defaultdict(int)
    assist_counts: dict[tuple[str, str], int] = defaultdict(int)
    assist_points: dict[tuple[str, str], int] = defaultdict(int)

    def add_combo_points(points: int) -> None:
        if points <= 0 or len(on_court) != 5:
            return
        players = tuple(sorted(on_court))
        for size in (2, 3, 5):
            for combo in combinations(players, size):
                combo_points[combo] += points

    for event in events:
        action_type = event.get("actionType")
        event_tno = str(event.get("tno"))

        if action_type == "substitution" and event_tno == tno:
            pid = str(event.get("pno"))
            if event.get("subType") == "in":
                on_court.add(pid)
            elif event.get("subType") == "out":
                on_court.discard(pid)
            continue

        if action_type in POINTS_BY_ACTION_TYPE and event_tno == tno and event.get("success") == 1:
            add_combo_points(POINTS_BY_ACTION_TYPE[action_type])
            continue

        if action_type == "assist" and event_tno == tno:
            passer = str(event.get("pno"))
            scoring_event = events_by_number.get(event.get("previousAction"))
            if scoring_event is None:
                continue
            scorer = str(scoring_event.get("pno"))
            if scorer == passer:
                continue
            points = POINTS_BY_ACTION_TYPE.get(scoring_event.get("actionType"), 0)
            pair = tuple(sorted((passer, scorer)))
            assist_counts[pair] += 1
            assist_points[pair] += points

    # "pno" je stabilní jen v rámci tohohle zápasu - přeložíme na jména
    # hráčů, ať se to dá bezpečně sečíst i s ostatními zápasy sezóny.
    names = player_names(raw_json, tno)

    def to_names(pids: tuple[str, ...]) -> tuple[str, ...]:
        return tuple(sorted(names.get(pid, pid) for pid in pids))

    return LineupStats(
        tno=tno,
        combo_points={to_names(combo): pts for combo, pts in combo_points.items()},
        assist_counts={to_names(pair): count for pair, count in assist_counts.items()},
        assist_points={to_names(pair): pts for pair, pts in assist_points.items()},
    )


def merge_lineup_stats(stats_list: list[LineupStats]) -> LineupStats:
    """Sečte výsledky analyze_pbp z více zápasů (napříč sezónou)."""
    combo_points: dict[tuple[str, ...], int] = defaultdict(int)
    assist_counts: dict[tuple[str, str], int] = defaultdict(int)
    assist_points: dict[tuple[str, str], int] = defaultdict(int)

    for s in stats_list:
        for combo, points in s.combo_points.items():
            combo_points[combo] += points
        for pair, count in s.assist_counts.items():
            assist_counts[pair] += count
        for pair, points in s.assist_points.items():
            assist_points[pair] += points

    return LineupStats(
        tno="",
        combo_points=dict(combo_points),
        assist_counts=dict(assist_counts),
        assist_points=dict(assist_points),
    )


def top_combos(combo_points: dict[tuple[str, ...], int], size: int, limit: int = 10) -> list[tuple[tuple[str, ...], int]]:
    """Vrátí nejlepších `limit` kombinací dané velikosti (2, 3 nebo 5) podle bodů."""
    filtered = [(combo, pts) for combo, pts in combo_points.items() if len(combo) == size]
    return sorted(filtered, key=lambda item: item[1], reverse=True)[:limit]


def top_assist_pairs(assist_counts: dict[tuple[str, str], int], limit: int = 10) -> list[tuple[tuple[str, str], int]]:
    """Vrátí nejlepších `limit` asistenčních dvojic podle počtu nahrávek."""
    return sorted(assist_counts.items(), key=lambda item: item[1], reverse=True)[:limit]
